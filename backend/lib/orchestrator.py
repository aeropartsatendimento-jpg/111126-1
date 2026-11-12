"""The squad engine — runs missions end-to-end in the background.

Flow: the Chefe dispatches a mission (optionally inside a project) → Zero
(cloud LLM) decomposes it, using the project's resume card as context →
each agent executes its task → tasks land in 'review' (an answer is not a
delivery) until the Chefe approves → approval updates the project's
'last verified delivery'.

Every LLM call degrades to simulated content on failure, so the flow always
completes and the room always tells the story.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument

from lib.brain import llm_json, llm_text
from lib.dates import today_iso
from lib.db import db
from lib.search import web_search
from routers.routing import routing_auto, tier_model

logger = logging.getLogger(__name__)

DELEGATABLE = ("pro", "jarvis", "aluna", "plus")
_BG: set[asyncio.Task] = set()  # keep refs so background tasks are not GC'd


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _BG.add(task)
    task.add_done_callback(_BG.discard)


PLAN_SYSTEM = (
    "Você é o Zero, a IA principal do esquadrão do Chefe (operação AeroPartz). Seu braço direito é o Pro, que supervisiona "
    "os agentes operacionais: Jarvis (tarefas simples, cálculos, scripts), Luna (atendimento comercial e site da AeroPartz) "
    "e Plus (executor analítico, versão enxuta do Pro). O Chefe manda a missão e VOCÊ a decompõe e delega.\n"
    "Responda SOMENTE com um JSON válido, sem markdown, no formato:\n"
    '{"intro": "1-2 frases anunciando o plano", '
    '"tasks": [{"agent_key": "pro|jarvis|aluna|plus", "title": "título curto", "detail": "o que fazer e qual o critério de entrega", "tier": "reasoning|fast"}], '
    '"next_step": "próximo passo do projeto depois desta missão", '
    '"decision_needed": "decisão que só o Chefe pode tomar, ou string vazia"}\n'
    "Regras: no máximo 4 tarefas; 'aluna' é a Luna (loja/site/atendimento); 'jarvis' rápidas; 'plus' análise; "
    "'pro' supervisão/consolidação. 'tier' é 'reasoning' para análise/decisão/planejamento, 'fast' para execução simples/busca/listagem. "
    "Nunca invente preços, estoque ou fatos comerciais — use só os dados fornecidos. "
    "Escreva tudo em português do Brasil."
)

EXEC_SYSTEM = (
    "Você é {name}, {role} do esquadrão coordenado pelo Zero e pelo Pro. Execute a tarefa delegada "
    "com seu raciocínio, em português do Brasil, direto ao ponto, no máximo 90 palavras. Traga resultado, "
    "decisão ou próximos passos concretos. Não invente dados comerciais; se faltar dado, diga exatamente qual."
)

ROOM_REPLY_SYSTEM = (
    "Você é o Zero, a IA principal do esquadrão (braço direito: Pro; operacionais: Jarvis, Luna, Plus). "
    "O Chefe falou na sala compartilhada. Responda em português do Brasil, no máximo 80 palavras, "
    "dizendo como o esquadrão vai agir (ofereça transformar em missão formal quando fizer sentido)."
)

DIRECT_SYSTEM = (
    "Você é o Zero, coordenador pessoal do Chefe — linha direta 1-a-1, estilo telefonema. Português do Brasil, "
    "tom parceiro e direto. Você coordena Pro, Jarvis, Luna e Plus.\n"
    "Classifique SUA resposta com uma intenção:\n"
    "- explicando: responder/informar, sem ação.\n"
    "- propondo: sugerir uma ação que precisa do OK do Chefe (preencha 'mission').\n"
    "- executando: o Chefe deu uma ORDEM clara (ex: 'faça', 'continue', 'verifique'); você dispara a missão agora (preencha 'mission').\n"
    "Nunca transforme comentário ou pergunta em tarefa. Na dúvida, use propondo.\n"
    "Se o pedido for sobre um projeto da lista, use o id dele em project_id.\n"
    "Para perguntas 'por que escolhemos X?', responda com a decisão, a DATA e a FONTE da memória, separando "
    "decisão do Chefe, fato verificado, proposta não aprovada e informação antiga. Se não houver registro, diga que não há.\n"
    "Responda SOMENTE com JSON válido: "
    '{"intent": "explicando|propondo|executando", "reply": "fala curta (máx 90 palavras)", '
    '"mission": "texto da missão ou string vazia", "project_id": "id ou null"}'
)

BRIEFING_SYSTEM = (
    "Você é o Zero, agente pessoal do Chefe (loja AeroPartz). Monte o briefing da manhã em português do Brasil, "
    "objetivo, no máximo 160 palavras, seções curtas: Clima (com base na busca), Loja AeroPartz (use SÓ os dados do painel "
    "fornecidos: estoque crítico, pedidos em aberto, cupons ativos), Projetos (bloqueios/decisões), Prioridades de hoje. "
    "Não invente números. Se um dado vier marcado como exemplo, avise que é exemplo."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


async def _post_room(
    sender_key: str,
    kind: str,
    content: str,
    mission_id: str | None = None,
    message_id: str | None = None,
) -> None:
    doc = {
        "id": message_id or _new_id(),
        "sender_key": sender_key,
        "kind": kind,
        "content": content,
        "mission_id": mission_id,
        "created_at": _now(),
    }
    if message_id:
        await db.room_messages.update_one({"id": message_id}, {"$setOnInsert": doc}, upsert=True)
    else:
        await db.room_messages.insert_one(doc)


async def _agent(key: str) -> dict | None:
    return await db.agents.find_one({"key": key})


# ---------- shared context blocks ----------

async def store_context() -> str:
    items = await db.store_items.find().to_list(200)
    if not items:
        return "(painel da loja vazio)"
    lines = []
    labels = {"stock": "Estoque", "order": "Pedido", "coupon": "Cupom"}
    for it in items:
        relevant = (it["kind"], it["status"]) in {("stock", "critical"), ("order", "open"), ("coupon", "active")}
        if not relevant:
            continue
        tag = " [EXEMPLO]" if it.get("is_sample") else ""
        lines.append(f"- {labels.get(it['kind'], it['kind'])}: {it['title']} · {it.get('value', '')} · {it.get('detail', '')}{tag}")
    return "\n".join(lines) or "(nada crítico, nenhum pedido em aberto, nenhum cupom ativo)"


async def projects_context() -> str:
    projects = await db.projects.find({"status": {"$ne": "done"}}).to_list(30)
    if not projects:
        return "(nenhum projeto)"
    return "\n".join(
        f"- id={p['id']} · {p['name']} · objetivo: {p.get('objective', '')[:120]} · bloqueio: {p.get('blocker', '') or '—'}"
        for p in projects
    )


async def project_card(project: dict) -> str:
    recent = await db.tasks.find({"project_id": project["id"]}).sort("updated_at", -1).to_list(5)
    results = "\n".join(
        f"  · [{t['status']}] {t['agent_key']}: {t['title']} → {(t.get('result') or '')[:160]}" for t in recent
    ) or "  (sem tarefas anteriores)"
    return (
        f"PROJETO: {project['name']}\n"
        f"Objetivo atual: {project.get('objective') or '—'}\n"
        f"Última entrega verificada: {project.get('last_verified') or '—'}\n"
        f"Em andamento: {project.get('in_progress') or '—'}\n"
        f"Bloqueio/decisão: {project.get('blocker') or '—'}\n"
        f"Próximo passo: {project.get('next_step') or '—'}\n"
        f"Resultados recentes:\n{results}"
    )


async def remember(
    kind: str,
    title: str,
    content: str,
    source: str,
    project_id: str | None = None,
    memory_id: str | None = None,
) -> None:
    doc = {
        "id": memory_id or _new_id(), "kind": kind, "title": title[:200], "content": content[:3000], "source": source[:300],
        "project_id": project_id, "replaces": None, "superseded_by": None, "created_at": _now(),
    }
    if memory_id:
        await db.memories.update_one({"id": memory_id}, {"$setOnInsert": doc}, upsert=True)
    else:
        await db.memories.insert_one(doc)


async def memory_context() -> str:
    labels = {"decisao_chefe": "DECISÃO DO CHEFE", "fato_verificado": "FATO VERIFICADO", "proposta": "PROPOSTA (não aprovada)", "antiga": "ANTIGA (conferir)"}
    docs = await db.memories.find().sort("created_at", -1).to_list(25)
    if not docs:
        return "(memória vazia)"
    return "\n".join(
        f"- [{labels.get(m['kind'], m['kind'])}] {m['created_at'].strftime('%d/%m/%Y')} · {m['title']}: {m.get('content', '')[:160]} "
        f"(fonte: {m.get('source') or '—'}){' — SUBSTITUÍDA por decisão mais nova' if m.get('superseded_by') else ''}"
        for m in docs
    )


# ---------- missions ----------

async def start_mission(text: str, project_id: str | None = None, mission_id: str | None = None) -> dict:
    """Create a mission and run it in the background. Shared by REST, chat and MCP."""
    if project_id and not await db.projects.find_one({"id": project_id}):
        project_id = None
    doc = {"id": mission_id or str(uuid.uuid4()), "text": text, "status": "planning", "plan_intro": None, "project_id": project_id, "created_at": _now()}
    await db.missions.insert_one(dict(doc))
    spawn(run_mission(doc["id"]))
    return doc


def resume_text(project: dict) -> str:
    return (
        f"Continue o projeto {project['name']} de onde paramos: confira a última entrega verificada, "
        f"avance o próximo passo e me mostre o que precisa da minha decisão."
    )


def _sim_plan(text: str) -> dict:
    short = text.strip().replace("\n", " ")[:90]
    return {
        "intro": f"Missão recebida, Chefe. Assumo a coordenação de \"{short}\" e aciono o esquadrão agora.",
        "tasks": [
            {"agent_key": "pro", "title": "Supervisionar execução", "detail": f"Dividir em etapas e acompanhar: {short}"},
            {"agent_key": "jarvis", "title": "Executar tarefa operacional", "detail": f"Verificações simples de: {short}"},
            {"agent_key": "aluna", "title": "Cuidar da parte da loja/site", "detail": f"Preparar o conteúdo relacionado a: {short}"},
        ],
        "next_step": "Revisar as entregas do esquadrão",
        "decision_needed": "",
    }


def _sim_result(title: str, detail: str) -> str:
    return f"[modo simulado] \"{title}\" — levantei os pontos de \"{detail[:80]}\" e deixei para revisão do Chefe."


async def _execute_task(task: dict, context: str, agent: dict | None) -> None:
    title, detail = task["title"], task["detail"]
    await db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "working", "updated_at": _now()}})
    await asyncio.sleep(1.0)

    reply: str | None = None
    if agent:
        provider = agent.get("provider", "openai")
        model = agent.get("model", "gpt-5.4")
        # Per-task routing: when the Chefe turned it on, swap the model to the right tier (reasoning vs fast)
        # while keeping the agent's provider — so Jarvis stays Jarvis but on Haiku for a fast task.
        tier = task.get("tier")
        if tier in ("reasoning", "fast") and await routing_auto():
            override = tier_model(provider, tier)
            if override:
                model = override
        reply = await llm_text(
            EXEC_SYSTEM.format(name=agent["name"], role=agent.get("role_pt", "agente operacional")),
            f"{context}\n\nSua tarefa delegada: {title}\nDetalhes/critério: {detail or '—'}\n\nResponda com a execução.",
            session_id=f"task-{task['id']}",
            provider=provider,
            model=model,
        )
    simulated = reply is None
    if simulated:
        reply = _sim_result(title, detail)

    # An agent's answer is not a delivery: it waits for the Chefe's review.
    await db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "review", "result": reply, "updated_at": _now()}})
    await _post_room(
        task["agent_key"],
        "chat",
        f"Entrega para revisão: {title}\n\n{reply}",
        task["mission_id"],
        message_id=f"task-delivery-{task['id']}",
    )


async def _claim_mission(mission_id: str) -> dict | None:
    now = _now()
    return await db.missions.find_one_and_update(
        {
            "id": mission_id,
            "status": {"$in": ["planning", "delegating"]},
            "$or": [
                {"lease_until": {"$exists": False}},
                {"lease_until": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "runner_id": _new_id(),
                "lease_until": now + timedelta(minutes=10),
                "updated_at": now,
            },
            "$inc": {"run_attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )


async def run_mission(mission_id: str) -> None:
    mission = await _claim_mission(mission_id)
    if not mission:
        return
    try:
        text = mission["text"]
        project = await db.projects.find_one({"id": mission.get("project_id")}) if mission.get("project_id") else None
        await _post_room(
            "system",
            "system",
            "Missão recebida pelo Zero. Analisando e montando o plano de delegação...",
            mission_id,
            message_id=f"mission-received-{mission_id}",
        )

        context = f"Missão do Chefe: {text}"
        if project:
            context = f"{await project_card(project)}\n\n{context}"
        context += f"\n\nPainel da loja AeroPartz:\n{await store_context()}"

        task_docs = await db.tasks.find({"mission_id": mission_id}).sort("created_at", 1).to_list(20)
        if not task_docs:
            zero = await _agent("zero") or {}
            plan = llm_json(
                await llm_text(
                    PLAN_SYSTEM,
                    context,
                    session_id=f"plan-{mission_id}",
                    provider=zero.get("provider", "openai"),
                    model=zero.get("model", "gpt-5.4"),
                )
            )
            simulated_plan = plan is None or not isinstance(plan.get("tasks"), list) or not plan["tasks"]
            if simulated_plan:
                plan = _sim_plan(text)

            intro = str(plan.get("intro") or "").strip() or "Plano montado. Delegando ao esquadrão."
            decision = str(plan.get("decision_needed") or "").strip()
            next_step = str(plan.get("next_step") or "").strip()
            await db.missions.update_one(
                {"id": mission_id},
                {
                    "$set": {
                        "plan_intro": intro,
                        "decision_needed": decision,
                        "next_step": next_step,
                        "plan_simulated": simulated_plan,
                        "updated_at": _now(),
                    }
                },
            )
            for item in [item for item in plan.get("tasks", []) if isinstance(item, dict)][:4] or [{"agent_key": "pro", "title": "Supervisionar execução", "detail": text[:300]}]:
                key = item.get("agent_key") if item.get("agent_key") in DELEGATABLE else "pro"
                tier = item.get("tier") if item.get("tier") in ("reasoning", "fast") else None
                task_docs.append({
                    "id": _new_id(), "mission_id": mission_id, "mission_text": text, "agent_key": key,
                    "title": (str(item.get("title") or "Tarefa").strip()[:140] or "Tarefa"),
                    "detail": str(item.get("detail") or "").strip()[:800],
                    "tier": tier,
                    "status": "queued", "result": None, "project_id": mission.get("project_id"), "review_note": None,
                    "created_at": _now(), "updated_at": _now(),
                })
            await db.tasks.insert_many([dict(doc) for doc in task_docs])
            mission.update(
                plan_intro=intro,
                decision_needed=decision,
                next_step=next_step,
                plan_simulated=simulated_plan,
            )

        intro = mission.get("plan_intro") or "Plano montado. Delegando ao esquadrão."
        names = {"aluna": "Luna"}
        lines = [intro, ""] + [f"→ {names.get(doc['agent_key'], doc['agent_key'].capitalize())}: {doc['title']}" for doc in task_docs]
        if project:
            lines.insert(0, f"📁 {project['name']}")
        if mission.get("plan_simulated"):
            lines += ["", "(plano simulado — IA em nuvem indisponível agora)"]
        await _post_room("zero", "delegation", "\n".join(lines), mission_id, message_id=f"mission-delegation-{mission_id}")
        await db.missions.update_one(
            {"id": mission_id},
            {"$set": {"status": "delegating", "lease_until": _now() + timedelta(minutes=10), "updated_at": _now()}},
        )

        if any(doc.get("status") in {"queued", "working"} for doc in task_docs):
            await asyncio.sleep(1.5)
        for doc in task_docs:
            if doc.get("status") not in {"queued", "working"}:
                continue
            try:
                await _execute_task(doc, context, await _agent(doc["agent_key"]))
            except Exception as exc:
                logger.exception("task %s failed", doc["id"])
                await db.tasks.update_one(
                    {"id": doc["id"]},
                    {"$set": {"status": "failed", "result": f"Erro na execução: {exc}", "updated_at": _now()}},
                )

        final_tasks = await db.tasks.find({"mission_id": mission_id}).sort("created_at", 1).to_list(20)
        for doc in final_tasks:
            if doc.get("status") in {"review", "verified", "rejected"} and doc.get("result"):
                await _post_room(
                    doc["agent_key"],
                    "chat",
                    f"Entrega para revisão: {doc['title']}\n\n{doc['result']}",
                    mission_id,
                    message_id=f"task-delivery-{doc['id']}",
                )
        failed = sum(doc.get("status") == "failed" for doc in final_tasks)
        awaiting_review = sum(doc.get("status") == "review" for doc in final_tasks)
        decision = str(mission.get("decision_needed") or "").strip()
        if project:
            update = {"in_progress": f"{text[:200]} — {awaiting_review} entrega(s) aguardando revisão", "updated_at": _now()}
            if mission.get("next_step"):
                update["next_step"] = str(mission["next_step"])[:500]
            if decision:
                update["blocker"] = decision[:500]
            await db.projects.update_one({"id": project["id"]}, {"$set": update})

        summary = f"Resumo do Zero: {awaiting_review} entrega(s) aguardando sua revisão em Tarefas"
        summary += f", {failed} falha(s)." if failed else "."
        if decision:
            summary += f"\n\n⚠️ Precisa da sua decisão: {decision}"
        await _post_room("system", "summary", summary, mission_id, message_id=f"mission-summary-{mission_id}")
        final_status = "failed" if final_tasks and failed == len(final_tasks) else "completed"
        await db.missions.update_one(
            {"id": mission_id},
            {
                "$set": {"status": final_status, "updated_at": _now()},
                "$unset": {"runner_id": "", "lease_until": "", "last_run_error": ""},
            },
        )
    except Exception as exc:
        logger.exception("mission %s interrupted", mission_id)
        await db.missions.update_one(
            {"id": mission_id},
            {
                "$set": {"last_run_error": type(exc).__name__, "updated_at": _now()},
                "$unset": {"runner_id": "", "lease_until": ""},
            },
        )


async def complete_review_effects(task: dict) -> dict:
    """Apply review side effects idempotently for a claimed terminal decision."""
    approve = task["status"] == "verified"
    note = task.get("review_note")
    if approve and task.get("project_id"):
        await db.projects.update_one(
            {"id": task["project_id"]},
            {"$set": {"last_verified": f"{task['title']} — {(task.get('result') or '').replace('**', '')[:240]}", "last_verified_at": _now(), "updated_at": _now()}},
        )
    if approve:
        await remember(
            "fato_verificado",
            task["title"],
            (task.get("result") or "").replace("**", ""),
            f"Entrega de {task['agent_key']} aprovada pelo Chefe (tarefa {task['id'][:8]})",
            task.get("project_id"),
            memory_id=f"task-review-{task['id']}",
        )
    verdict = "✅ aprovou" if approve else "↩️ devolveu"
    await _post_room(
        "user",
        "system",
        f"Chefe {verdict} a entrega \"{task['title']}\"" + (f": {note}" if note else "."),
        task.get("mission_id"),
        message_id=f"task-review-{task['id']}",
    )
    await db.tasks.update_one(
        {"id": task["id"], "review_effects": "pending"},
        {"$set": {"review_effects": "completed", "updated_at": _now()}},
    )
    return await db.tasks.find_one({"id": task["id"]})


async def review_task(task_id: str, approve: bool, note: str | None) -> dict | None:
    status = "verified" if approve else "rejected"
    task = await db.tasks.find_one_and_update(
        {"id": task_id, "status": "review"},
        {"$set": {"status": status, "review_note": note, "review_effects": "pending", "updated_at": _now()}},
        return_document=ReturnDocument.AFTER,
    )
    if not task:
        return None
    return await complete_review_effects(task)


# ---------- conversations ----------

async def _claim_pending_reply(collection, source_id: str, response_id: str) -> bool:
    if await collection.find_one({"id": response_id}, {"_id": 1}):
        await collection.update_one(
            {"id": source_id},
            {"$set": {"reply_status": "completed", "updated_at": _now()}, "$unset": {"reply_lease_until": ""}},
        )
        return False
    now = _now()
    claimed = await collection.find_one_and_update(
        {
            "id": source_id,
            "reply_status": {"$in": ["pending", "working"]},
            "$or": [
                {"reply_lease_until": {"$exists": False}},
                {"reply_lease_until": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "reply_status": "working",
                "reply_lease_until": now + timedelta(minutes=5),
                "updated_at": now,
            },
            "$inc": {"reply_attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    return claimed is not None


async def _complete_pending_reply(collection, source_id: str) -> None:
    await collection.update_one(
        {"id": source_id},
        {"$set": {"reply_status": "completed", "updated_at": _now()}, "$unset": {"reply_lease_until": ""}},
    )


async def zero_reply_in_room(source_message_id: str | None = None) -> None:
    response_id = f"room-reply-{source_message_id}" if source_message_id else None
    if source_message_id and not await _claim_pending_reply(db.room_messages, source_message_id, response_id):
        return
    recent = await db.room_messages.find().sort("created_at", -1).to_list(12)
    transcript = "\n".join(f"{m.get('sender_key', '?')}: {m.get('content', '')[:300]}" for m in reversed(recent))
    zero = await _agent("zero") or {}
    reply = await llm_text(
        ROOM_REPLY_SYSTEM, f"Últimas mensagens da sala:\n{transcript}\n\nResponda ao Chefe.",
        session_id=f"room-{_new_id()}", provider=zero.get("provider", "openai"), model=zero.get("model", "gpt-5.4"),
    )
    if reply is None:
        reply = "[modo simulado] Entendido, Chefe. Se quiser, transforme isso em missão no Cockpit que eu delego agora."
    await _post_room("zero", "chat", reply, message_id=response_id)
    if source_message_id:
        await _complete_pending_reply(db.room_messages, source_message_id)


async def zero_direct_reply(source_message_id: str | None = None) -> None:
    response_id = f"zero-reply-{source_message_id}" if source_message_id else None
    if source_message_id and not await _claim_pending_reply(db.zero_messages, source_message_id, response_id):
        return
    recent = await db.zero_messages.find().sort("created_at", -1).to_list(10)
    transcript = "\n".join(f"{'Chefe' if m.get('role') == 'user' else 'Zero'}: {m.get('content', '')[:400]}" for m in reversed(recent))
    zero = await _agent("zero") or {}
    raw = await llm_text(
        DIRECT_SYSTEM,
        f"Projetos:\n{await projects_context()}\n\nPainel da loja:\n{await store_context()}\n\n"
        f"Memória (com data e fonte):\n{await memory_context()}\n\nConversa:\n{transcript}\n\nResponda ao Chefe.",
        session_id=f"direct-{_new_id()}", provider=zero.get("provider", "openai"), model=zero.get("model", "gpt-5.4"),
    )
    data = llm_json(raw)
    msg = {"id": response_id or _new_id(), "role": "zero", "intent": "explicando", "proposal": None, "project_id": None, "mission_id": None, "created_at": _now()}
    if data and str(data.get("reply") or "").strip():
        intent = data.get("intent") if data.get("intent") in ("explicando", "propondo", "executando") else "explicando"
        mission_text = str(data.get("mission") or "").strip()
        pid = data.get("project_id") if isinstance(data.get("project_id"), str) else None
        msg.update(content=str(data["reply"]).strip(), intent=intent, project_id=pid)
        if intent in ("propondo", "executando") and mission_text:
            msg["proposal"] = mission_text[:1500]
            if intent == "executando":
                deterministic_mission_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"qg-zero-direct:{source_message_id}")) if source_message_id else None
                mission = await db.missions.find_one({"id": deterministic_mission_id}) if deterministic_mission_id else None
                if not mission:
                    mission = await start_mission(mission_text[:1500], pid, mission_id=deterministic_mission_id)
                msg["mission_id"] = mission["id"]
                last_user = next((m for m in recent if m.get("role") == "user"), None)
                await remember("decisao_chefe", mission_text[:120], (last_user or {}).get("content", "")[:1000],
                               "Ordem do Chefe na Linha Direta", pid,
                               memory_id=f"direct-order-{source_message_id}" if source_message_id else None)
        elif intent != "explicando":
            msg["intent"] = "explicando"
    elif raw:
        msg["content"] = raw.strip()
    else:
        msg["content"] = "[modo simulado] Estou online, Chefe. Mande a ordem que eu organizo o esquadrão."
    if response_id:
        await db.zero_messages.update_one({"id": response_id}, {"$setOnInsert": msg}, upsert=True)
        await _complete_pending_reply(db.zero_messages, source_message_id)
    else:
        await db.zero_messages.insert_one(msg)


async def run_briefing(
    settings: dict,
    day: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Morning routine: real weather search + store panel + projects → Zero's briefing, posted to the room."""
    if idempotency_key:
        existing = await db.briefings.find_one({"id": idempotency_key})
        if existing:
            await _post_room(
                "zero",
                "briefing",
                f"🌅 Briefing da manhã ({existing['day']} — {existing.get('city', '')}):\n\n{existing['content']}",
                message_id=f"room-{idempotency_key}",
            )
            return existing

    city = settings.get("city", "São Paulo")
    hits = await web_search(f"previsão do tempo hoje {city}")
    search_block = "\n".join(f"- {h.title}: {h.snippet[:140]}" for h in hits[:5]) or "(busca indisponível agora)"

    zero = await _agent("zero") or {}
    reply = await llm_text(
        BRIEFING_SYSTEM,
        f"Clima — busca real para {city}:\n{search_block}\n\nPainel da loja AeroPartz:\n{await store_context()}\n\n"
        f"Projetos:\n{await projects_context()}\n\nMonte o briefing da manhã.",
        session_id=f"briefing-{_new_id()}", provider=zero.get("provider", "openai"), model=zero.get("model", "gpt-5.4"),
    )
    if reply is None:
        reply = "[modo simulado] Bom dia, Chefe. Sem nuvem agora: confira o painel da loja e os bloqueios dos projetos."

    doc = {
        "id": idempotency_key or _new_id(),
        "day": day or today_iso("America/Sao_Paulo"),
        "city": city,
        "content": reply,
        "created_at": _now(),
    }
    if idempotency_key:
        await db.briefings.update_one({"id": idempotency_key}, {"$setOnInsert": dict(doc)}, upsert=True)
        doc = await db.briefings.find_one({"id": idempotency_key}) or doc
    else:
        await db.briefings.insert_one(dict(doc))
    await _post_room(
        "zero",
        "briefing",
        f"🌅 Briefing da manhã ({doc['day']} — {doc.get('city', city)}):\n\n{doc['content']}",
        message_id=f"room-{idempotency_key}" if idempotency_key else None,
    )
    return doc
