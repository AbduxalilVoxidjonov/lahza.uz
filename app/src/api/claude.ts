// "Claude montaj" bo'limi: `/v1/claude/*` (holat, yoqish, login tekshiruvi, MCP ulash/uzish).
// Claude onlayn xizmat - standart o'chiq; yoqilganda faqat timeline tavsifi va transkript matni yuboriladi.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { parseClaudeStatus, parseConnectResult, type ClaudeStatus, type ClaudeTarget } from "../lib/claude";
import { get, post, put } from "./client";

export const claudeStatusKey = ["claude", "status"] as const;

export const useClaudeStatus = () =>
  useQuery({
    queryKey: claudeStatusKey,
    queryFn: async () => parseClaudeStatus(await get<unknown>("/v1/claude/status")),
    retry: false,
  });

function useStatusMutation<V>(fn: (vars: V) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: V) => parseClaudeStatus(await fn(vars)),
    onSuccess: (data: ClaudeStatus) => qc.setQueryData(claudeStatusKey, data),
  });
}

export const useSetClaudeEnabled = () =>
  useStatusMutation((enabled: boolean) => put<unknown>("/v1/claude/settings", { enabled }));

export const useCheckClaudeAuth = () => useStatusMutation(() => post<unknown>("/v1/claude/check-auth"));

export interface ClaudeConnectBody {
  target: ClaudeTarget;
  dry_run: boolean;
}

/** `connect` yoki `disconnect`: avval `dry_run: true` (amallar ro'yxati), so'ng haqiqiy chaqiruv. */
export function useClaudeConnection(kind: "connect" | "disconnect") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClaudeConnectBody) => parseConnectResult(await post<unknown>(`/v1/claude/${kind}`, body)),
    onSuccess: (res) => qc.setQueryData(claudeStatusKey, res.status),
  });
}
