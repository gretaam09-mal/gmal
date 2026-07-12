export function StalenessBanner({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return null;
  return (
    <div className="flex flex-col gap-2 rounded-md border border-amber-300 bg-amber-50 p-3">
      <p className="font-ui text-xs font-semibold uppercase tracking-wide text-amber-800">
        Inputs changed
      </p>
      <ul className="flex flex-col gap-1">
        {reasons.map((reason) => (
          <li key={reason} className="font-ui text-xs text-amber-800">
            {reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
