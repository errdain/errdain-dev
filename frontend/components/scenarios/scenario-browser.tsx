"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { titleCase } from "@/lib/utils";
import type { Domain, ScenarioLibrarySummary } from "@/types/api";

const domains: ("all" | Domain)[] = ["all", "retail", "banking", "healthcare", "manufacturing", "telecommunications", "logistics", "finance", "insurance", "education", "ecommerce"];

function readableText(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\brecord records\b/gi, "records")
    .replace(/\bkyc\b/gi, "KYC")
    .replace(/\bsms\b/gi, "SMS")
    .replace(/\bsla\b/gi, "SLA")
    .replace(/\bOut Of\b/g, "Out of")
    .replace(/\s+/g, " ")
    .trim();
}

function scenarioTitle(scenario: ScenarioLibrarySummary) {
  const name = readableText(scenario.scenario_name);
  const entity = titleCase(readableText(scenario.entity));
  return name.toLowerCase().includes(entity.toLowerCase()) ? name : `${name}: ${entity}`;
}

export function ScenarioBrowser({
  scenarios,
  selectedId,
  domain,
  onDomainChange,
  onSelect,
}: {
  scenarios: ScenarioLibrarySummary[];
  selectedId?: string;
  domain: "all" | Domain;
  onDomainChange: (domain: "all" | Domain) => void;
  onSelect: (scenarioId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const visibleScenarios = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return scenarios;
    return scenarios.filter((scenario) =>
      [
        scenario.scenario_name,
        scenario.description,
        scenario.domain,
        scenario.business_process,
        scenario.failure_display_name,
      ].some((value) => value.toLowerCase().includes(normalizedQuery)),
    );
  }, [query, scenarios]);

  return (
    <section data-testid="scenario-browser" className="flex max-h-[70vh] min-h-0 flex-col rounded-3xl border border-border bg-card p-4 shadow-sm xl:sticky xl:top-4 xl:h-[calc(100vh-2rem)] xl:max-h-[calc(100vh-2rem)]">
      <div className="shrink-0">
        <div className="mb-3 flex items-center justify-between gap-3 px-1">
          <div>
            <h2 className="font-semibold">Scenario Library</h2>
            <p className="text-xs text-muted-foreground">Browse all scenarios or filter by domain.</p>
          </div>
          <Badge>{scenarios.length}</Badge>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row xl:flex-col 2xl:flex-row">
        <label className="min-w-0 flex-1 text-sm">
          <span className="mb-1 block text-xs font-semibold text-muted-foreground">Search scenarios</span>
          <div className="flex h-11 items-center gap-2 rounded-2xl border border-border bg-background px-3 text-muted-foreground">
            <Search className="h-4 w-4" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search scenarios and descriptions"
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-xs font-semibold text-muted-foreground">Browse by domain</span>
          <select value={domain} onChange={(event) => onDomainChange(event.target.value as "all" | Domain)} className="h-11 w-full rounded-2xl border border-border bg-background px-3 sm:w-56">
            {domains.map((item) => (
              <option key={item} value={item}>{item === "all" ? "All domains" : titleCase(item)}</option>
            ))}
          </select>
        </label>
        </div>
      </div>

      <div data-testid="scenario-scroll-list" className="mt-4 grid min-h-0 flex-1 content-start gap-3 overflow-y-auto overscroll-contain pr-2">
        <p className="px-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Showing {visibleScenarios.length} of {scenarios.length} available scenarios
        </p>
        {visibleScenarios.map((scenario) => (
          <button
            key={scenario.scenario_id}
            onClick={() => onSelect(scenario.scenario_id)}
            className={`rounded-2xl border p-4 text-left transition hover:border-primary ${selectedId === scenario.scenario_id ? "border-primary bg-primary/5" : "border-border bg-background"}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold"><span className="text-muted-foreground">Scenario:</span> {scenarioTitle(scenario)}</p>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted-foreground"><span className="font-semibold text-foreground">Description:</span> {readableText(scenario.description)}</p>
              </div>
              <Badge>{titleCase(scenario.domain)}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              <Badge>{titleCase(scenario.business_process)}</Badge>
              <Badge>{scenario.failure_display_name}</Badge>
              <Badge>{scenario.v1_ready ? "V1 Ready" : "Experimental"}</Badge>
            </div>
          </button>
        ))}
        {visibleScenarios.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-muted-foreground">
            No scenarios match this search in the selected domain.
          </p>
        ) : null}
      </div>
    </section>
  );
}
