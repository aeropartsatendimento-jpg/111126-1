# QG do Zero — Relatório de estado atual

## Resumo

O núcleo do QG está funcional e validado em modo simulado. A rodada mais recente concluiu estados localizados
de carregamento, vazio, indisponibilidade e dados antigos nas dez áreas principais, com recuperação sem recarregar.
Depois dessa validação, P1.4–P1.7 receberam novas implementações que ainda aguardam a bateria agrupada combinada.

## Pronto e testado

- Acesso aberto ao QG, sem autenticação.
- Cockpit, missões, decomposição simulada, delegação e tarefas.
- Sala Compartilhada e Linha Direta.
- Revisão de entregas com aprovação/devolução.
- Proteção atômica contra duas revisões simultâneas.
- Proteção atômica contra duas execuções da mesma proposta.
- Memórias e mensagens de revisão idempotentes.
- Projetos, retomada, contas salvas e Memória com Origem.
- Briefing manual e configuração da rotina da manhã.
- Painel AeroPartz com estoque, pedidos e cupons locais.
- Canais cadastrados e busca DuckDuckGo com fallback seguro.
- Servidor MCP do QG implementado e protegido por token quando configurado.
- Navegador Visual simulado com URL, objetivo, histórico, quatro etapas e publicação na Sala.
- Seleção das ações simuladas: **abrir, ler, clicar, escrever, copiar e colar**.
- Persistência de tipo, alvo, status e saída de cada ação.
- Compatibilidade com missões visuais antigas sem o campo `actions`.
- Rotina automática resistente a reinícios, respeitando `auto`, horário configurável e `America/Sao_Paulo`.
- Entregas repetidas do cron e retomadas após falha não duplicam briefing nem mensagem na Sala.
- Cockpit, Sala, Projetos, Tarefas, Linha Direta, Navegador, Loja, Canais, Universo e Memória preservam o shell em falhas.
- Cada consulta indisponível oferece nova tentativa; cache anterior permanece visível e explicitamente marcado como antigo.

## Implementado e aguardando validação

- P1.4: mobile, teclado, foco, skip-link, alvos de toque e movimento reduzido.
- P1.5: recuperação persistente de ações com preservação de entrada e alerta de duplicidade.
- P1.6: Saúde do QG, última atualização, histórico local, atualizar tudo e limpar histórico.
- P1.7: retomada após reinício de missões, tarefas, revisões, propostas, conversas e missões visuais.
- Estes itens **não pertencem ainda à lista “Pronto e testado”** e não devem ser tratados como concluídos antes do ensaio agrupado.

## Garantias do Navegador Visual atual

- Toda a interface e entrega mostram **MODO SIMULADO**.
- Nenhuma requisição é enviada ao host informado.
- Nenhum DOM, tela, login, cookie ou conta real é lido.
- Nenhum clique, escrita, cópia ou colagem acontece em site real.
- A API rejeita ação desconhecida, lista vazia e tipos duplicados com 422.
- O relatório da Sala inclui somente as ações escolhidas.

## Evidências mais recentes

- `test_reports/iteration_8.json`: **8/8 critérios de interface aprovados**, sem falhas ou bloqueios.
- Recuperação sem reload, regiões independentes, vazio versus falha, cache antigo, PT/EN e teclado foram validados.
- `test_reports/iteration_7.json`: **7/7 critérios aprovados**; suíte backend completa **36/36**.
- Gate local: autenticação/validação/duplicata do webhook, TypeScript e jornada Cockpit → Sala aprovados.
- `test_reports/iteration_5.json`: **6/6 critérios aprovados**, sem falhas ou bloqueios.
- `test_reports/iteration_4.json`: concorrência de revisão/proposta aprovada.
- `test_reports/iteration_3.json`: fluxo original do Navegador Visual aprovado.
- TypeScript e gate de navegador passaram sem erros de console ou HTTP inesperados.

## Simulado ou ainda não conectado

- Cérebro dos agentes: usa fallback **SIMULADO** quando a chave de IA não está ativa.
- Navegador Visual: ações são sintéticas; não existe controle real de navegador.
- WhatsApp, Facebook e conexão com MCP/navegador da VPS: ainda não operam canais reais.
- Itens iniciais do painel AeroPartz: exemplos marcados `is_sample=true`.
- Loja AeroPartz real: sem sincronização externa.

## Próximos passos de maior valor

1. Executar uma única bateria agrupada para P1.4–P1.7, incluindo reinício controlado e viewport móvel.
2. Corrigir somente os defeitos encontrados e marcar como concluído o que tiver evidência.
3. Depois da validação, escolher uma integração real; navegador/MCP, loja e canais exigem URLs, acesso e decisões do Chefe.

## Registro de continuidade — 11/11/2026

- Tarefa: P1.2 concluída.
- Arquivos principais: `.emergent/crons.yml`, `backend/routers/cron.py`, `backend/lib/scheduler.py`,
  `backend/lib/orchestrator.py`, `backend/server.py`, contratos e índices.
- Testes: gate local aprovado; Testing Agent 7/7; suíte backend 36/36; navegador aprovado.
- Ambiente: seed idempotente reaplicado; agentes, canais, projetos e exemplos restaurados sem apagar dados existentes.
- Próximo passo exato: iniciar P1.3, estados de erro e recuperação visíveis.

## Registro de continuidade — 12/11/2026

- Tarefa: P1.3 concluída (Fase 1 de erros e recuperação).
- Arquivos principais: `frontend/src/components/DataRegionState.tsx`, páginas do QG e `frontend/src/lib/i18n.tsx`.
- Testes: gate proporcional aprovado; Testing Agent 8/8; regressão backend 36/36.
- Próximo passo exato: iniciar P1.4, cobertura móvel e acessibilidade.

## Registro de continuidade — 12/11/2026 · P1.4 em validação

- Implementado: foco visível global, alvos de toque, filtros roláveis, formulários móveis e navegação inferior com snap.
- Acessibilidade adicional: skip-link, nomes bilíngues em controles por ícone, alvos de 44px no Universo e movimento reduzido.
- Jornada AeroPartz: ordem de Tab do formulário da Loja preserva item → quantidade/valor → adicionar.
- Estado: código aplicado, **não validado nesta rodada por decisão do Chefe de agrupar os testes mais adiante**.
- Próximo passo exato: continuar o desenvolvimento desejado e, na rodada combinada, validar P1.4 em mobile/teclado antes de marcar concluído.

## Registro de continuidade — 12/11/2026 · P1.5 em validação

- Implementado: `ActionErrorNotice.tsx`, aviso persistente e bilíngue com repetir/fechar e alerta de duplicidade.
- Cobertura: missão, briefing, Sala, Linha Direta, execução de proposta, Navegador Visual, projetos, contas,
  revisão de tarefas, Loja, canais, busca e Memória.
- Preservação: campos só são limpos no sucesso; falha de busca mantém resultados anteriores visíveis.
- Estado: código aplicado, **não validado nesta rodada para manter a bateria agrupada solicitada pelo Chefe**.
- Próximo passo exato: implementar diagnóstico operacional simples (saúde e última atualização) ou iniciar a bateria agrupada quando o Chefe pedir.

## Registro de continuidade — 12/11/2026 · P1.6 em validação

- Implementado: card “Saúde do QG” no Cockpit para seis áreas essenciais.
- Estados: disponível, verificando, dados antigos, indisponível e não verificado, com última atualização bem-sucedida.
- Histórico: até oito transições recentes guardadas no navegador; quatro exibidas sem detalhes técnicos.
- Ações: atualização manual das seis áreas e limpeza do histórico local.
- Estado: código aplicado e **ainda não validado**, incluído na bateria agrupada solicitada pelo Chefe.
- Próximo passo exato: tornar missões/tarefas em andamento recuperáveis após reinício do backend.

## Registro de continuidade — 13/11/2026 · Bateria P1.4–P1.7 + troca de modelo por agente

- **P1.4–P1.7 validados**: Testing Agent `iteration_9.json` = **8/8 passed**, 0 bugs, 0 bloqueios, retest_needed=false.
  Cobertura: mobile/teclado (390x844), recuperação de mutation com preserve-input + retry, Saúde do QG com histórico,
  retomada após `sudo supervisorctl restart backend` sem duplicar missão/entrega/resumo (IDs determinísticos).
  Suíte backend completa: **40/40** (3 novos arquivos).
- **Novo feature "Trocar cérebro por agente"**: `PATCH /api/agents/{key}` valida provider ∈ {openai, anthropic, gemini},
  model obrigatório, brain opcional com default por par (provider,model). UI: `AgentModelEditor` no Cockpit, abre dialog
  com select de provider, input de modelo + sugestões (gpt-5.4, claude-sonnet-5-5, gemini-3-flash-preview), input de rótulo.
  Toast de sucesso/erro, invalida `['agents']`. Sem reseed.
- **Seed atualizado** e aplicado: jarvis/aluna/plus em `anthropic/claude-sonnet-5-5`; zero/pro seguem em `openai/gpt-5.4`.
- **Brain em nuvem**: decisão do Chefe — permanece em modo SIMULADO nesta rodada. `/api/system` retorna
  `brain=simulated` e nenhuma rota quebra; validado pela bateria.
- **Melhoria registrada (não bug)**: React dev-warning "Cannot update OperationalHealthCard while rendering RoomStream"
  no mobile-keyboard check; sem efeito para o usuário.
- Arquivos: `backend/models/models.py`, `backend/routers/agents.py`, `backend/seed.py`,
  `frontend/src/lib/types.ts`, `frontend/src/components/AgentModelEditor.tsx`,
  `frontend/src/pages/Cockpit.tsx`, `frontend/src/lib/i18n.tsx`, `backend/.env` (recriado mínimo),
  `memory/SPEC.md`, `memory/RELATORIO_ESTADO.md`, `memory/test_credentials.md`.
- Próximo passo exato: habilitar `EMERGENT_LLM_KEY` pelo painel seguro quando o Chefe quiser sair do SIMULADO,
  e `QG_MCP_TOKEN` para expor o servidor MCP a clientes externos.

## Registro de continuidade — 12/11/2026 · P2.1 Claude adicionado (parcial)

- Integrações ChatGPT (OpenAI) e Claude (Anthropic) via `emergentintegrations` prontas na mesma `lib/brain.py`.
- Seed atualizado: Jarvis/Luna/Plus passaram de `gemini / gemini-3-flash-preview` para `anthropic / claude-sonnet-5-5`;
  Zero/Pro seguem em `openai / gpt-5.4`. Infra de provider/model por agente já existia.
- Chave: `EMERGENT_LLM_KEY` gerenciada pelo Emergent. A chave de teste atual está com budget 0 e produz
  erro `Budget has been exceeded!`; sem chave ativa, `GET /api/system` reporta `brain=simulated` e o fallback
  SIMULADO continua operante (comportamento esperado por SPEC).
- Arquivos alterados: `backend/.env` (recriado mínimo), `backend/seed.py`, `memory/SPEC.md`, `memory/RELATORIO_ESTADO.md`.
- Próximo passo exato: Chefe habilita a chave universal real (ou própria) pelo painel seguro; depois rodar missão
  de sanidade pelo Cockpit e confirmar `brain=cloud` com resposta real de ambos os provedores.

## Registro de continuidade — 12/11/2026 · P1.7 em validação

- Implementado: leases de execução e recuperação no startup para missões normais e visuais interrompidas.
- Idempotência: mensagens de recebimento, delegação, entrega, resumo e entrega visual têm IDs determinísticos.
- Retomada: ignora tarefas/etapas concluídas, retoma `queued|working`, completa revisão pendente e proposta reservada.
- Conversas: mensagens da Sala e Linha Direta mantêm job de resposta persistido e resposta determinística; ordens diretas
  também reutilizam a mesma missão e memória após reinício.
- Arquivos: `backend/lib/recovery.py`, `backend/lib/orchestrator.py`, `backend/routers/visual.py`, `backend/server.py`, índices.
- Estado: código aplicado, **ainda não validado em reinício controlado** por decisão de agrupar testes.
- Próximo passo exato: executar a bateria agrupada P1.4–P1.7 antes de qualquer integração real ou publicação.

## Referências

- Especificação viva: `memory/SPEC.md`
- Cronograma: `memory/CRONOGRAMA.md`
- Relatório de teste atual: `test_reports/iteration_5.json`