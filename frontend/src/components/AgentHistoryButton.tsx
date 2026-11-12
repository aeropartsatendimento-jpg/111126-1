import { useQuery } from "@tanstack/react-query";
import { History, LoaderCircle, ArrowRight } from "lucide-react";

import { apiGet } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatWhen } from "@/lib/format";
import type { Agent, AgentModelChange } from "@/lib/types";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import BrainBadge from "@/components/BrainBadge";

export default function AgentHistoryButton({ agent }: { agent: Agent }) {
  const { lang } = useI18n();

  const query = useQuery({
    queryKey: ["agent-history", agent.key],
    queryFn: () => apiGet<AgentModelChange[]>(`/agents/${agent.key}/history?limit=10`),
    enabled: false, // only fetches when the popover opens
    staleTime: 15_000,
  });

  const label = lang === "pt" ? "Histórico de trocas" : "Change history";
  const emptyCopy = lang === "pt" ? "Nenhuma troca registrada." : "No changes yet.";
  const errorCopy = lang === "pt" ? "Não foi possível carregar o histórico." : "Could not load the history.";

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={`${label} — ${agent.name}`}
            data-testid={`agent-history-btn-${agent.key}`}
            onClick={() => {
              // Defer to next tick so React doesn't see a state update while rendering AgentHistoryButton.
              setTimeout(() => void query.refetch(), 0);
            }}
          >
            <History className="size-3.5" />
          </Button>
        }
      />
      <PopoverContent
        align="end"
        side="bottom"
        sideOffset={6}
        className="w-80 p-0"
        data-testid={`agent-history-popover-${agent.key}`}
      >
        <div className="border-b px-3 py-2 text-xs font-semibold text-slate-700">
          {label} · {agent.name}
        </div>
        <div className="max-h-72 overflow-y-auto">
          {query.isFetching ? (
            <div className="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground">
              <LoaderCircle className="size-3.5 animate-spin" />
              {lang === "pt" ? "Carregando..." : "Loading..."}
            </div>
          ) : query.isError ? (
            <div className="px-3 py-4 text-xs text-destructive" data-testid={`agent-history-error-${agent.key}`}>
              {errorCopy}
            </div>
          ) : !query.data || query.data.length === 0 ? (
            <div className="px-3 py-4 text-xs text-muted-foreground" data-testid={`agent-history-empty-${agent.key}`}>
              {emptyCopy}
            </div>
          ) : (
            <ul className="divide-y" data-testid={`agent-history-list-${agent.key}`}>
              {query.data.map((row) => (
                <li
                  key={row.id}
                  className="space-y-1 px-3 py-2 text-xs"
                  data-testid={`agent-history-row-${row.id}`}
                >
                  <div className="flex items-center gap-1.5 font-mono">
                    <BrainBadge provider={row.from_provider} model={row.from_model} size="xs" />
                    <ArrowRight className="size-3 text-muted-foreground" />
                    <BrainBadge provider={row.to_provider} model={row.to_model} size="xs" />
                  </div>
                  <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                    <span className="truncate font-mono">
                      {row.from_model || "—"} → {row.to_model}
                    </span>
                    <span className="shrink-0">{formatWhen(row.created_at, lang)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
