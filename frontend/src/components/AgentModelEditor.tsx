import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, LoaderCircle } from "lucide-react";
import { toast } from "sonner";

import { apiPatch } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Agent, AgentModelUpdate } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ProviderKey = "openai" | "anthropic" | "gemini";

const PROVIDER_LABELS: Record<ProviderKey, string> = {
  openai: "ChatGPT (OpenAI)",
  anthropic: "Claude (Anthropic)",
  gemini: "Gemini (Google)",
};

const MODEL_SUGGESTIONS: Record<ProviderKey, { value: string; label: string }[]> = {
  openai: [
    { value: "gpt-5.4", label: "gpt-5.4" },
    { value: "gpt-5.4-mini", label: "gpt-5.4-mini" },
    { value: "gpt-5.5", label: "gpt-5.5" },
  ],
  anthropic: [
    { value: "claude-sonnet-5-5", label: "Claude Sonnet 5.5" },
    { value: "claude-haiku-5-5", label: "Claude Haiku 5.5" },
    { value: "claude-opus-5-5", label: "Claude Opus 5.5" },
  ],
  gemini: [
    { value: "gemini-3-flash-preview", label: "Gemini 3 Flash (preview)" },
    { value: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro (preview)" },
  ],
};

export default function AgentModelEditor({ agent }: { agent: Agent }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState<ProviderKey>((agent.provider as ProviderKey) || "openai");
  const [model, setModel] = useState(agent.model);
  const [brain, setBrain] = useState(agent.brain);

  useEffect(() => {
    if (open) {
      setProvider((agent.provider as ProviderKey) || "openai");
      setModel(agent.model);
      setBrain(agent.brain);
    }
  }, [open, agent]);

  const mutation = useMutation({
    mutationFn: (body: AgentModelUpdate) => apiPatch<Agent>(`/agents/${agent.key}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      toast.success(lang === "pt" ? "Modelo atualizado" : "Model updated");
      setOpen(false);
    },
    onError: () => {
      toast.error(lang === "pt" ? "Não foi possível atualizar o modelo" : "Could not update the model");
    },
  });

  const providerOptions: ProviderKey[] = ["openai", "anthropic", "gemini"];
  const modelSuggestions = MODEL_SUGGESTIONS[provider] ?? [];

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!model.trim()) return;
    mutation.mutate({ provider, model: model.trim(), brain: brain.trim() || null });
  };

  const titleCopy = lang === "pt" ? "Trocar cérebro de" : "Change brain of";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto shrink-0"
            data-testid={`agent-edit-model-${agent.key}`}
            aria-label={`${titleCopy} ${agent.name}`}
          >
            <Pencil className="size-3.5" />
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md" data-testid={`agent-edit-dialog-${agent.key}`}>
        <DialogHeader>
          <DialogTitle>
            {titleCopy} {agent.name}
          </DialogTitle>
          <DialogDescription>
            {lang === "pt"
              ? "Escolha o provedor e o modelo. A mudança vale para a próxima missão deste agente."
              : "Pick the provider and model. The change applies to this agent's next mission."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={`provider-${agent.key}`}>{lang === "pt" ? "Provedor" : "Provider"}</Label>
            <Select
              value={provider}
              onValueChange={(v: string) => {
                const next = (providerOptions.includes(v as ProviderKey) ? v : "openai") as ProviderKey;
                setProvider(next);
                const first = MODEL_SUGGESTIONS[next]?.[0]?.value;
                if (first) setModel(first);
              }}
            >
              <SelectTrigger id={`provider-${agent.key}`} data-testid={`agent-edit-provider-${agent.key}`}>
                <SelectValue>{(v) => PROVIDER_LABELS[v as ProviderKey] ?? "—"}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {providerOptions.map((p) => (
                  <SelectItem key={p} value={p}>
                    {PROVIDER_LABELS[p]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={`model-${agent.key}`}>{lang === "pt" ? "Modelo" : "Model"}</Label>
            <Input
              id={`model-${agent.key}`}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={modelSuggestions[0]?.value}
              data-testid={`agent-edit-model-input-${agent.key}`}
              required
            />
            {modelSuggestions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {modelSuggestions.map((m) => (
                  <Button
                    key={m.value}
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={() => setModel(m.value)}
                    data-testid={`agent-edit-model-suggest-${agent.key}-${m.value}`}
                  >
                    {m.label}
                  </Button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={`brain-${agent.key}`}>{lang === "pt" ? "Rótulo do cérebro" : "Brain label"}</Label>
            <Input
              id={`brain-${agent.key}`}
              value={brain}
              onChange={(e) => setBrain(e.target.value)}
              placeholder={lang === "pt" ? "Ex.: Claude Sonnet" : "e.g. Claude Sonnet"}
              data-testid={`agent-edit-brain-input-${agent.key}`}
            />
            <p className="text-xs text-muted-foreground">
              {lang === "pt"
                ? "Opcional. Em branco, uso um padrão pelo provedor/modelo."
                : "Optional. Leave empty to use a default label for provider/model."}
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              data-testid={`agent-edit-cancel-${agent.key}`}
            >
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={mutation.isPending || !model.trim()}
              data-testid={`agent-edit-save-${agent.key}`}
            >
              {mutation.isPending && <LoaderCircle className="mr-1.5 size-4 animate-spin" />}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
