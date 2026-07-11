"use client";

import { inferFieldKind } from "../fieldKind";
import type { FieldCatalogEntry, ProfileField } from "../types";
import { SourceBadge } from "./SourceBadge";

interface Props {
  spec: FieldCatalogEntry;
  field: ProfileField | undefined;
  onChange: (key: string, value: unknown, source: "user" | "unknown") => void;
}

export function FieldRow({ spec, field, onChange }: Props) {
  const kind = inferFieldKind(spec.key);
  const value = field?.value;
  const source = field?.source ?? "unknown";

  return (
    <div className="flex flex-col gap-1.5 border-b border-ink/5 py-3 last:border-b-0">
      <div className="flex items-center justify-between gap-2">
        <span className="font-ui text-sm text-ink">{spec.label}</span>
        <SourceBadge source={source} />
      </div>
      {spec.used_for ? <p className="font-ui text-xs text-ink/50">{spec.used_for}</p> : null}

      {kind === "boolean" ? (
        <div className="flex gap-2">
          {(["Yes", "No", "Unknown"] as const).map((option) => {
            const optionValue = option === "Yes" ? true : option === "No" ? false : null;
            const selected =
              option === "Unknown" ? source === "unknown" : source !== "unknown" && value === optionValue;
            return (
              <button
                key={option}
                type="button"
                onClick={() =>
                  onChange(spec.key, optionValue, option === "Unknown" ? "unknown" : "user")
                }
                className={`rounded-md border px-3 py-1 font-ui text-xs ${
                  selected
                    ? "border-primary-navy bg-primary-navy text-paper"
                    : "border-ink/20 text-ink/70 hover:bg-ink/5"
                }`}
              >
                {option}
              </button>
            );
          })}
        </div>
      ) : kind === "readonly-list" ? (
        <p className="font-ui text-sm text-ink/70">
          {Array.isArray(value) && value.length > 0
            ? value
                .map((item) => (typeof item === "string" ? item : (item as { name?: string }).name))
                .join(", ")
            : "Not yet available"}
        </p>
      ) : (
        <input
          type={kind === "number" ? "number" : "text"}
          value={typeof value === "string" || typeof value === "number" ? value : ""}
          placeholder="Unknown"
          onChange={(event) => {
            const raw = event.target.value;
            const parsed = kind === "number" ? (raw === "" ? null : Number(raw)) : raw || null;
            onChange(spec.key, parsed, parsed === null ? "unknown" : "user");
          }}
          className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
        />
      )}
    </div>
  );
}
