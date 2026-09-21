export function EvidenceRoleChip(_props: { view?: string; role?: string }) {
  return null;
}

export function ControlEvidenceKind({ where }: { where: "workbench" | "evidence" }) {
  return (
    <section className="ce-kinds" data-control={`control.evidence-kinds.${where}`} aria-label="Kinds of control evidence">
      <div className="meta">This panel is not part of the public release.</div>
    </section>
  );
}
