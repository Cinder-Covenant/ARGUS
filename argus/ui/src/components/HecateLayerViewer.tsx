/*
 * A bounded view of one already-produced Hecate control-run receipt.
 *
 * Lists identity-bound Hecate receipts and exposes one governed, hash-bound
 * PHerc0139 apparatus-control execution. Other scrolls remain display only.
 *
 * The receipt's own `exposure` and `scientific_state` fields decide what may be claimed about
 * the output (for the current n1926 control: "APPARATUS ONLY / EXPOSED DIRECT"), and that
 * label sits next to the image -- not only inside the provenance panel -- so a probability map
 * cannot be mistaken for a reading, a qualified detector, or evidence of generalization. A
 * scroll or acquisition with no registered receipt gets an explicit empty state naming why;
 * it is never answered with a different scroll's or acquisition's cached output.
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Chip } from "./Status";
import { PlanApprove } from "./PlanApprove";
import { isRefusal, readGovernedJob, type GovernedJob, type GovernedResult, type GovernedRefusal } from "../lib/governed";

const CONTROL_ID = "local-control-0139-title-native9362";
type ControlRequest = Record<string, string | number | boolean>;

interface InventoryEntry {
  physical_scroll: string;
  acquisition_id: string;
  provider?: string;
  exposure?: string;
  scientific_state?: string;
  label?: string;
}

interface Inventory {
  selected_scroll: string | null;
  canonical_scroll: string | null;
  available: boolean;
  entries: InventoryEntry[];
  why?: string | null;
}

interface ImageRef {
  path: string;
  sha256?: string | null;
  orientation: string;
}

interface VolumeRef {
  path: string;
  orientation: string;
  file_count?: number;
}

interface Layer {
  schema: string;
  physical_scroll: string;
  acquisition_id: string;
  run_id?: string | null;
  provider?: string | null;
  provider_revision?: string | null;
  checkpoint_sha256?: string | null;
  spacing_um?: number | null;
  receipt_path: string;
  orientation: {
    primary: string;
    secondary: string;
    decision_rule?: string | null;
    construction_trust?: string | null;
  };
  image: { primary: ImageRef; secondary: ImageRef | null };
  volume_3d: { primary: VolumeRef | null; secondary: VolumeRef | null };
  exposure: string;
  scientific_state: string;
  claim_ceiling: string;
  eligible_for_automatic_routing: boolean;
  label: string;
}

interface Refused {
  state: "REFUSED";
  why: string;
}

function isRefused(x: Layer | Refused): x is Refused {
  return (x as Refused).state === "REFUSED";
}

const Z_DEPTH = 16; // the n1926 control's declared central_depth; a future receipt with a
// different depth still bounds its own slider via `activeVolume`'s reported shape once one
// exists on the wire -- kept fixed here only until a receipt declares its own depth.

export function HecateLayerViewer({ selectedScroll }: { selectedScroll: string | null }) {
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [layer, setLayer] = useState<Layer | Refused | null>(null);
  const [showSecondary, setShowSecondary] = useState(false);
  const [show3d, setShow3d] = useState(false);
  const [z, setZ] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const refreshInventory = useCallback(() => setRefreshVersion((v) => v + 1), []);

  useEffect(() => {
    setInventory(null);
    setLayer(null);
    setShowSecondary(false);
    setShow3d(false);
    setZ(0);
    setError(null);
    if (!selectedScroll) return;
    let cancelled = false;
    fetch(`/api/providers/hecate/layer_inventory?scroll=${encodeURIComponent(selectedScroll)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: Inventory) => {
        if (!cancelled) setInventory(d);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedScroll, refreshVersion]);

  useEffect(() => {
    if (!inventory || !selectedScroll || !inventory.available) return;
    // The identity check already happened on the service (`inventory.canonical_scroll`); this
    // only picks WHICH of this scroll's registered acquisitions to load. There is no
    // first-available fallback across scrolls -- `inventory.entries` is already filtered to
    // this scroll by the service.
    const entry = inventory.entries[0];
    if (!entry) return;
    let cancelled = false;
    const q = new URLSearchParams({ scroll: selectedScroll, acquisition_id: entry.acquisition_id });
    fetch(`/api/providers/hecate/layer?${q.toString()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: Layer | Refused) => {
        if (!cancelled) setLayer(d);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [inventory, selectedScroll]);

  const controlAlreadyRegistered = Boolean(inventory?.entries.some((entry) => entry.acquisition_id === CONTROL_ID));
  const controlPanel = selectedScroll === "PHerc0139" ? (
    <HecateControlRunPanel alreadyRegistered={controlAlreadyRegistered} onComplete={refreshInventory} />
  ) : null;

  if (!selectedScroll)
    return <Empty title="No scroll is selected" body="Select a physical scroll before opening Hecate output." />;
  if (error) return <>{controlPanel}<Empty title="The Hecate output could not be read" body={error} /></>;
  if (!inventory)
    return <>{controlPanel}<Empty title="Reading Hecate output" body="Checking for an identity-matched Hecate run…" /></>;
  if (!inventory.available)
    return (
      <>{controlPanel}<Empty
          title={`No Hecate output is registered for ${selectedScroll}`}
          body={inventory.why ?? "The service did not find an identity-matched Hecate run."}
        /></>
    );
  if (!layer)
    return <>{controlPanel}<Empty title="Reading Hecate output" body="Loading the identity-matched run receipt…" /></>;
  if (isRefused(layer))
    return <>{controlPanel}<Empty title={`Hecate output for ${selectedScroll} was refused`} body={layer.why} /></>;

  const active = showSecondary ? layer.image.secondary : layer.image.primary;
  const activeOrientation = active?.orientation ?? layer.orientation.primary;
  const activeVolume = showSecondary ? layer.volume_3d.secondary : layer.volume_3d.primary;
  const imageUrl = active ? api.fileUrl(active.path) : null;

  return (
    <>
    {controlPanel}
    <section className="ag-fiber-view" aria-label="Hecate control-run output preview">
      <div className="ag-viewbar" role="group" aria-label="Hecate output provenance">
        <span className="ag-viewbar-label">
          {layer.run_id ?? layer.provider} · {layer.physical_scroll}/{layer.acquisition_id}
        </span>
        <Chip tone="blocked" size="sm">
          {layer.label}
        </Chip>
        {layer.image.secondary ? (
          <button type="button" className="ag-btn" onClick={() => setShowSecondary((v) => !v)}>
            {showSecondary
              ? `Show ${layer.orientation.primary} (primary)`
              : `Show ${layer.orientation.secondary} (secondary)`}
          </button>
        ) : null}
        {activeVolume ? (
          <button type="button" className="ag-btn" aria-pressed={show3d} onClick={() => setShow3d((v) => !v)}>
            {show3d ? "Hide 3-D" : "3-D view"}
          </button>
        ) : null}
      </div>
      <div className="ag-fiber-image-wrap">
        {show3d && activeVolume ? (
          <figure style={{ display: "grid", gap: 8, justifyItems: "center", margin: 0 }}>
            <img
              src={`/api/providers/hecate/layer_3d_slice?scroll=${encodeURIComponent(
                layer.physical_scroll,
              )}&acquisition_id=${encodeURIComponent(layer.acquisition_id)}&orientation=${
                showSecondary ? "secondary" : "primary"
              }&z=${z}`}
              alt={`Grayscale z=${z} slice of the declared 3-D ${activeOrientation} output`}
              className="ag-fiber-image"
            />
            <input
              type="range"
              min={0}
              max={Z_DEPTH - 1}
              value={z}
              onChange={(e) => setZ(Number(e.target.value))}
              aria-label="3-D depth slice"
            />
            <span className="small faint">z = {z}</span>
          </figure>
        ) : imageUrl ? (
          <img
            src={imageUrl}
            alt={`Hecate ${activeOrientation} probability-map output for ${layer.physical_scroll}, apparatus-control run only`}
            className="ag-fiber-image"
          />
        ) : null}
      </div>
      <div className="ag-fiber-note">
        <strong>{layer.label} — not a reading.</strong> {layer.claim_ceiling}
        <span className="meta">
          {" "}
          checkpoint {layer.checkpoint_sha256 ? `${layer.checkpoint_sha256.slice(0, 12)}…` : "unrecorded"} · revision{" "}
          {layer.provider_revision ?? "unrecorded"} · spacing {layer.spacing_um ?? "?"} µm · orientation{" "}
          {activeOrientation} (construction trust: {layer.orientation.construction_trust ?? "not established"}) ·
          receipt <span className="mono">{layer.receipt_path}</span>
        </span>
      </div>
    </section>
    </>
  );
}

function HecateControlRunPanel({
  alreadyRegistered,
  onComplete,
}: {
  alreadyRegistered: boolean;
  onComplete: () => void;
}) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GovernedJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submissionRefused, setSubmissionRefused] = useState<string | null>(null);
  const [completionNotified, setCompletionNotified] = useState(false);
  const [controlRequest, setControlRequest] = useState<ControlRequest | null>(null);
  const [controlWhy, setControlWhy] = useState<string | null>(null);

  useEffect(() => {
    if (alreadyRegistered || jobId) return;
    let cancelled = false;
    fetch("/api/providers/hecate/control_request")
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((data: { available: boolean; request?: ControlRequest; why?: string }) => {
        if (cancelled) return;
        if (data.available && data.request) setControlRequest(data.request);
        else setControlWhy(data.why ?? "The retained control is not configured on this machine.");
      })
      .catch((e) => { if (!cancelled) setControlWhy(String(e)); });
    return () => { cancelled = true; };
  }, [alreadyRegistered, jobId]);

  const submitted = useCallback((result: GovernedResult | GovernedRefusal) => {
    if (isRefusal(result)) {
      setSubmissionRefused(result.reason);
      return;
    }
    const nested = result.result;
    const duplicate = nested.job as GovernedJob | undefined;
    const nextId = nested.job_id ?? duplicate?.job_id;
    if (typeof nextId === "string") {
      setSubmissionRefused(null);
      setJobId(nextId);
      setJob(duplicate ?? null);
    }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      const latest = await readGovernedJob(jobId);
      if (stopped) return;
      if (isRefusal(latest)) {
        setError(latest.reason);
        return;
      }
      setError(null);
      setJob(latest);
      if (latest.state === "RUNNING") {
        timer = setTimeout(poll, 1000);
      } else if (latest.state === "SUCCEEDED" && !completionNotified) {
        setCompletionNotified(true);
        onComplete();
      }
    };
    void poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, completionNotified, onComplete]);

  const progress = job?.progress ?? {};
  const completed = Number(progress.completed_tiles ?? 0);
  const total = Number(progress.total_tiles ?? 49);
  const running = job?.state === "RUNNING";

  return (
    <section className="ag-panel" aria-label="Run retained Hecate control" data-testid="hecate-control-runner">
      <h3 className="ag-panel-title">Pinned Hecate 9.6 µm control</h3>
      <p className="ag-prose">
        One retained, already exposed PHerc0139 positive-control field. This checks the real reader,
        governed job, tiling, paired output writer and viewer. It is not target inference or an ink reading.
      </p>
      {alreadyRegistered ? (
        <p className="small faint">This single-use control already has a registered receipt; no second run is offered.</p>
      ) : jobId ? (
        <div className="meta" role="status" data-testid="hecate-control-job-state">
          {running ? `Job ${jobId}: ${String(progress.phase ?? "starting")} — ${completed}/${total} tiles.` :
            `Job ${jobId}: ${job?.state ?? "checking"}.`}
          {error ? ` Status polling: ${error}` : null}
        </div>
      ) : null}
      {submissionRefused ? <p className="meta" role="alert">Refused: {submissionRefused}</p> : null}
      {!alreadyRegistered && !jobId && controlWhy ? <p className="small faint">{controlWhy}</p> : null}
      {!alreadyRegistered && !jobId && controlRequest ? (
        <PlanApprove
          action="provider.candidate.invoke"
          params={{ provider_id: "hecate_96um", request: controlRequest }}
          label="the retained PHerc0139 control"
          why="runs only the hash-bound retained PHerc0139 control with pinned Hecate 9.6 µm; no other scroll or input can execute"
          inlineOperatorKeyEntry
          onSubmitted={submitted}
        />
      ) : null}
      {running ? (
        <PlanApprove action="job.cancel" params={{ job_id: jobId }} label="cancel this control job"
          why="requests a cooperative stop at the next tile boundary; partial output is not presented as complete" />
      ) : null}
      {job?.state === "SUCCEEDED" ? (
        <p className="small faint">Receipt and outputs are in this job’s fresh control directory. The identity-matched viewer is below.</p>
      ) : null}
      {job && ["REFUSED", "FAILED", "CANCELLED"].includes(job.state) ? (
        <p className="small faint">No completed control is claimed. Preserve the job and log, fix a demonstrated defect, then request any further run separately.</p>
      ) : null}
    </section>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="ag-panel" data-testid="hecate-layer-state">
      <h3 className="ag-panel-title">{title}</h3>
      <p className="ag-prose">{body}</p>
      <p className="small faint">This is an asset or identity state, not an absent Hecate finding.</p>
    </div>
  );
}
