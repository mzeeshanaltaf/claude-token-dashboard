import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmt } from "@/lib/format";

export interface TurnTokens {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_create_5m_tokens: number;
  cache_create_1h_tokens: number;
  cost_input_usd?: number | null;
  cost_output_usd?: number | null;
  cost_cache_read_usd?: number | null;
  cost_cache_create_5m_usd?: number | null;
  cost_cache_create_1h_usd?: number | null;
  estimated_cost_usd?: number | null;
}

/** Tokens and cost per token type for one assistant turn. */
export function TurnBreakdown({ t }: { t: TurnTokens }) {
  const rows: [string, string, number, number | null | undefined][] = [
    ["Input", "var(--chart-input)", t.input_tokens, t.cost_input_usd],
    ["Output", "var(--chart-output)", t.output_tokens, t.cost_output_usd],
    ["Cache read", "var(--chart-cache-read)", t.cache_read_tokens, t.cost_cache_read_usd],
    ["Cache write (5m)", "var(--chart-cache-write)", t.cache_create_5m_tokens, t.cost_cache_create_5m_usd],
    ["Cache write (1h)", "var(--chart-cache-write)", t.cache_create_1h_tokens, t.cost_cache_create_1h_usd],
  ];
  const total = rows.reduce((s, r) => s + r[2], 0);
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="text-xs">Type</TableHead>
          <TableHead className="text-right text-xs">Tokens</TableHead>
          <TableHead className="text-right text-xs">Cost</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(([label, color, tokens, cost]) => (
          <TableRow key={label} className="hover:bg-transparent">
            <TableCell className="text-xs">
              <span className="flex items-center gap-2">
                <span aria-hidden className="size-2 rounded-[2px]" style={{ background: color }} />
                {label}
              </span>
            </TableCell>
            <TableCell className="text-right font-mono text-xs tabular">{fmt.int(tokens)}</TableCell>
            <TableCell className="text-right font-mono text-xs tabular">{fmt.usd4(cost)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
      <TableFooter>
        <TableRow className="hover:bg-transparent">
          <TableCell className="text-xs font-medium">Total</TableCell>
          <TableCell className="text-right font-mono text-xs tabular">{fmt.int(total)}</TableCell>
          <TableCell className="text-right font-mono text-xs font-medium tabular">{fmt.usd4(t.estimated_cost_usd)}</TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  );
}
