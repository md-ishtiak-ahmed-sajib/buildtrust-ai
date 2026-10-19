import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Search as SearchIcon, Plus } from "lucide-react";
import { useWorkspace } from "../App";
import { api, post, formatMoney, titleCase } from "../api";
import { Panel, Modal, Loading, ErrorState, Status } from "../ui";
import { Field, Facts, useAction, text, type Material, type Comparison, type Offer, type Search, type Estimate } from "./shared";
import { QuoteForm } from "./QuoteForm";

export function PriceDrawer({
  material,
  estimate,
  lineId,
  componentId,
  quantity = "1",
  onSelected,
  onClose,
}: {
  material: Material;
  estimate?: Estimate;
  lineId?: string;
  componentId?: string;
  quantity?: string;
  onSelected?: (e: Estimate) => void;
  onClose: () => void;
}) {
  const { user } = useWorkspace(),
    client = useQueryClient(),
    action = useAction();
  const [mode, setMode] = useState<"LIVE" | "DEMO">("LIVE"),
    [qty, setQty] = useState(quantity),
    [city, setCity] = useState("Dhaka"),
    [country, setCountry] = useState("BD"),
    [location, setLocation] = useState("Dhaka"),
    [searchId, setSearchId] = useState<number>(),
    [filter, setFilter] = useState(""),
    [source, setSource] = useState("ALL"),
    [match, setMatch] = useState("ALL"),
    [sort, setSort] = useState("recommended"),
    [reason, setReason] = useState(""),
    [confirm, setConfirm] = useState<Offer>(),
    [technicalReview, setTechnicalReview] = useState<Offer>(),
    [technicalReason, setTechnicalReason] = useState(""),
    [quoteOpen, setQuoteOpen] = useState(false),
    [compared, setCompared] = useState<number[]>([]);
  const task = useQuery({
    queryKey: ["price-search", searchId],
    queryFn: () => api<Search>(`/prices/searches/${searchId}`),
    enabled: !!searchId,
    refetchInterval: (q) =>
      ["QUEUED", "RUNNING"].includes(q.state.data?.status || "") ? 1000 : false,
  });
  const selectionPreview = useQuery({
    queryKey: [
      "price-selection-preview",
      estimate?.id,
      estimate?.version,
      confirm?.observation_id,
    ],
    queryFn: () =>
      post<Record<string, unknown>>(
        `/materials/${material.id}/prices/preview`,
        {
          estimate_id: estimate!.id,
          expected_version: estimate!.version,
          line_id: lineId,
          component_id: componentId,
          observation_id: confirm!.observation_id,
          search_id: searchId,
        },
      ),
    enabled: !!confirm && !!estimate,
  });
  const prices = useQuery({
    queryKey: [
      "material-prices",
      material.id,
      searchId,
      task.data?.updated_at,
      mode,
    ],
    queryFn: () =>
      api<Comparison>(
        `/materials/${material.id}/prices?${searchId ? `search_id=${searchId}` : `mode=${mode}&quantity=${encodeURIComponent(qty)}&city=${encodeURIComponent(city)}&country=${country}`}`,
      ),
  });
  const running = ["QUEUED", "RUNNING"].includes(task.data?.status || "");
  const offers = (prices.data?.offers || [])
    .filter(
      (o) =>
        (source === "ALL" || o.source_type === source) &&
        (match === "ALL" || o.compatibility === match) &&
        `${o.payload.supplier} ${o.payload.title}`
          .toLowerCase()
          .includes(filter.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "cost"
        ? Number(a.landed_unit_cost ?? Infinity) -
          Number(b.landed_unit_cost ?? Infinity)
        : Number(b.recommended) - Number(a.recommended) ||
          Number(b.score) - Number(a.score),
    );
  const canWrite = user.role !== "AUDITOR";
  const refresh = () =>
    action.run(async () => {
      const task = await post<Search>(
        `/materials/${material.id}/prices/refresh`,
        {
          mode,
          quantity: qty,
          unit: material.unit,
          currency: prices.data?.currency || "BDT",
          city,
          country,
          delivery_location: location,
        },
      );
      setSearchId(task.id);
      await client.invalidateQueries({ queryKey: ["material-prices"] });
    }, "Search request recorded");
  const oldLine = (estimate?.fields.lines || []).find((l) => l.id === lineId),
    component = (oldLine?.components || []).find((c) => c.id === componentId);
  return (
    <Modal title="Material price comparison" onClose={onClose}>
      <div className="price-drawer">
        <div className="advanced-hero">
          <span className="eyebrow">SOURCE-BACKED RATE SELECTION</span>
          <h2>{material.name}</h2>
          <p>
            {Object.entries(material.specification)
              .map(([k, v]) => `${titleCase(k)}: ${v}`)
              .join(" · ")}{" "}
            · Canonical unit: {material.unit}
          </p>
        </div>
        <div className="advanced-grid search-controls">
          <Field label="Source mode">
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value as typeof mode);
                setSearchId(undefined);
              }}
            >
              <option value="LIVE">Online / verified sources</option>
              <option value="DEMO">Synthetic demonstration catalogue</option>
            </select>
          </Field>
          <Field label={`Quantity (${material.unit})`}>
            <input value={qty} onChange={(e) => setQty(e.target.value)} />
          </Field>
          <Field label="Country code">
            <input
              value={country}
              maxLength={2}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
            />
          </Field>
          <Field label="City">
            <input value={city} onChange={(e) => setCity(e.target.value)} />
          </Field>
          <Field label="Delivery location">
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </Field>
          <button
            className="button primary"
            disabled={!canWrite || action.busy || running}
            onClick={() => void refresh()}
          >
            <SearchIcon size={16} /> Search prices
          </button>
          <button className="button light" disabled={!canWrite || action.busy}
            onClick={() => void action.run(async () => {
              await post(`/materials/${material.id}/history/refresh`);
              await prices.refetch();
            }, "Approved purchase history refreshed; existing snapshots retained")}>Refresh internal history</button>
        </div>
        {mode === "DEMO" && (
          <div className="notice">
            Synthetic demonstration prices. These are not live listings or
            verified merchant offers.
          </div>
        )}
        {task.data && (
          <div className="advanced-task">
            <Status value={task.data.status} />
            {Object.entries(task.data.states).map(([name, state]) => (
              <span key={name}>
                {name}: {text((state as { status: string }).status)}
              </span>
            ))}
            {["WAITING", "INTERRUPTED", "FAILED"].includes(
              task.data.status,
            ) && (
              <button
                className="button light"
                onClick={() =>
                  void action.run(async () => {
                    await post(`/prices/searches/${task.data!.id}/retry`);
                    await task.refetch();
                  })
                }
              >
                Resume known task
              </button>
            )}
          </div>
        )}
        {action.feedback}
        {prices.error && <ErrorState error={prices.error} onRetry={() => { void prices.refetch(); }} />}
        {prices.isPending && <Loading />}
        {prices.data && (
          <p className="muted" role="status">
            Displayed search: {String(prices.data.displayed_request?.quantity)}{" "}
            {String(prices.data.displayed_request?.unit || material.unit)} ·{" "}
            {String(prices.data.displayed_request?.city)},{" "}
            {String(prices.data.displayed_request?.country)} ·{" "}
            {String(prices.data.displayed_request?.mode)} ·{" "}
            {prices.data.searched_at ||
              "Stored observations; no search selected"}
          </p>
        )}
        {prices.data?.notice && (
          <div className="notice">
            {prices.data.notice}{" "}
            {!offers.length &&
              "Try a supplier quotation, official reference import or historical rate."}
          </div>
        )}
        <div className="advanced-inline price-filters">
          <input
            aria-label="Filter quotation results"
            placeholder="Filter supplier or product"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <select
            aria-label="Filter price source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="ALL">All source categories</option>
            {[
              "ONLINE_LISTING",
              "SUPPLIER_QUOTE",
              "OFFICIAL_REFERENCE",
              "HISTORICAL_INTERNAL",
              "DEMO",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Filter technical match"
            value={match}
            onChange={(e) => setMatch(e.target.value)}
          >
            <option value="ALL">All technical matches</option>
            {[
              "Exact Match",
              "Approved Equivalent",
              "Incompatible",
              "Insufficient Information",
              "Requires Technical Review",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Sort quotations"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="recommended">Recommendation</option>
            <option value="cost">Comparable landed cost</option>
          </select>
        </div>
        {!!compared.length && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Selected comparison</th>
                  <th>Technical match</th>
                  <th>Landed unit cost</th>
                  <th>Evidence score</th>
                </tr>
              </thead>
              <tbody>
                {offers
                  .filter((o) => compared.includes(o.observation_id))
                  .map((o) => (
                    <tr key={o.observation_id}>
                      <td>{text(o.payload.supplier)}</td>
                      <td>{o.compatibility}</td>
                      <td>{o.landed_unit_cost || "Unknown"}</td>
                      <td>{o.score} / 100</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="quote-cards">
          {offers.map((o) => (
            <article
              key={o.observation_id}
              className={`quote-card ${o.recommended ? "recommended" : ""}`}
            >
              <div className="quote-card-head">
                <div>
                  <span className="eyebrow">
                    {titleCase(o.source_type)}
                    {o.recommended ? " · Recommended" : ""}
                    {o.lowest_comparable ? " · Lowest comparable" : ""}
                  </span>
                  <h3>{text(o.payload.supplier)}</h3>
                  <p>{text(o.payload.title)}</p>
                </div>
                <span className={`compatibility ${o.eligible ? "good" : ""}`}>
                  {o.compatibility}
                </span>
              </div>
              <div className="quote-costs">
                <div>
                  <small>Original price</small>
                  <strong>
                    {text(o.payload.currency)} {text(o.payload.price)} /{" "}
                    {text(o.payload.unit)}
                  </strong>
                </div>
                <div>
                  <small>Normalized product price</small>
                  <strong>
                    {o.normalized_unit_price
                      ? formatMoney(o.normalized_unit_price)
                      : "Unavailable"}{" "}
                    / {material.unit}
                  </strong>
                </div>
                <div>
                  <small>Landed unit cost · {prices.data?.currency}</small>
                  <strong>
                    {o.landed_unit_cost
                      ? formatMoney(o.landed_unit_cost)
                      : "Partially comparable"}
                  </strong>
                </div>
              </div>
              <ul className="quote-reasons">
                {o.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
              <p className="muted">
                {text(o.payload.city)} · Retrieved{" "}
                {new Date(o.retrieved_at).toLocaleString()} · Valid until{" "}
                {text(o.payload.valid_until)}
              </p>
              <details>
                <summary>Cost breakdown, conversions and evidence</summary>
                <Facts
                  data={{
                    ...o.cost_breakdown,
                    conversions: o.conversions,
                    specification: o.payload.specification,
                    scoring: o.scoring,
                    evidence_hash: o.evidence_hash,
                  }}
                />
              </details>
              <div className="advanced-inline">
                {o.payload.source_url ? (
                  <a
                    className="button light"
                    href={text(o.payload.source_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View source <ExternalLink size={14} />
                  </a>
                ) : (
                  <span className="muted">
                    {o.source_type === "DEMO"
                      ? "Synthetic catalogue evidence"
                      : "Attachment / internal evidence"}
                  </span>
                )}
                <button
                  className="button light"
                  onClick={() =>
                    setCompared((old) =>
                      old.includes(o.observation_id)
                        ? old.filter((id) => id !== o.observation_id)
                        : [...old, o.observation_id],
                    )
                  }
                >
                  {compared.includes(o.observation_id)
                    ? "Remove comparison"
                    : "Compare"}
                </button>
                {canWrite && estimate && (
                  <button
                    className="button primary"
                    disabled={!o.eligible || estimate.status !== "DRAFT"}
                    onClick={() => setConfirm(o)}
                  >
                    Use this price
                  </button>
                )}
                {canWrite && o.source_type === "ONLINE_LISTING" && (
                  <button
                    className="button light"
                    disabled={action.busy}
                    onClick={() =>
                      void action.run(async () => {
                        await post(
                          `/prices/observations/${o.observation_id}/quotation-draft`,
                        );
                        await client.invalidateQueries({
                          queryKey: ["quotations"],
                        });
                      }, "Quotation draft saved in Materials & Prices. Verify supplier and unknown charges before independent review.")
                    }
                  >
                    Prepare quotation draft
                  </button>
                )}
                {["ADMIN", "FINANCE_MANAGER"].includes(user.role) &&
                  [
                    "Incompatible",
                    "Requires Technical Review",
                    "Insufficient Information",
                  ].includes(o.compatibility) &&
                  o.payload.rate_category === "MATERIAL" && (
                    <button
                      className="button light"
                      onClick={() => setTechnicalReview(o)}
                    >
                      Review engineering equivalence
                    </button>
                  )}
              </div>
            </article>
          ))}
        </div>
        {technicalReview && (
          <section className="price-confirm">
            <h3>Independent engineering equivalence review</h3>
            <p>
              Confirm equivalence only with legitimate engineering evidence.
              Price similarity does not establish equivalence. Cost and delivery
              gates still apply.
            </p>
            <Field label="Engineering evidence and reason">
              <textarea
                value={technicalReason}
                onChange={(e) => setTechnicalReason(e.target.value)}
              />
            </Field>
            <div className="advanced-inline">
              <button
                className="button primary"
                disabled={action.busy || technicalReason.trim().length < 10}
                onClick={() =>
                  void action.run(async () => {
                    await post(`/materials/${material.id}/equivalents`, {
                      observation_id: technicalReview.observation_id,
                      reason: technicalReason,
                    });
                    setTechnicalReview(undefined);
                    setTechnicalReason("");
                    await prices.refetch();
                  }, "Independent equivalence recorded")
                }
              >
                Record reviewed equivalence
              </button>
              <button
                className="button light"
                onClick={() => setTechnicalReview(undefined)}
              >
                Cancel technical review
              </button>
            </div>
          </section>
        )}
        {canWrite && (
          <button
            className="button light"
            onClick={() => setQuoteOpen(!quoteOpen)}
          >
            <Plus size={15} /> Prepare supplier quotation / RFQ details
          </button>
        )}
        {quoteOpen && (
          <Panel title="Supplier quotation register">
            <p>
              Prepare the request or enter a supplier response locally. Nothing
              is sent to a supplier automatically.
            </p>
            <QuoteForm
              material={material}
              onSaved={() => {
                setQuoteOpen(false);
                void client.invalidateQueries({ queryKey: ["quotations"] });
              }}
            />
          </Panel>
        )}
        {confirm && estimate && (
          <section
            className="price-confirm"
            role="region"
            aria-label="Confirm selected rate"
          >
            <h3>Confirm estimate rate change</h3>
            {selectionPreview.isPending && <Loading />}
            {selectionPreview.error && (
              <ErrorState error={selectionPreview.error} onRetry={() => { void selectionPreview.refetch(); }} />
            )}
            {selectionPreview.data && (
              <Facts
                data={{
                  ...selectionPreview.data,
                  source: confirm.payload.supplier,
                }}
              />
            )}
            <p>
              The backend recalculates the item, estimate and scheduled
              forecast. Existing purchase orders and payments retain their
              authorized prices.
            </p>
            <Field label="Selection reason (required for a different eligible offer)">
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <div className="advanced-inline">
              <button
                className="button primary"
                disabled={action.busy || !selectionPreview.data}
                onClick={() =>
                  void action.run(async () => {
                    const updated = await post<Estimate>(
                      `/materials/${material.id}/prices/select`,
                      {
                        estimate_id: estimate.id,
                        expected_version: estimate.version,
                        line_id: lineId,
                        component_id: componentId,
                        observation_id: confirm.observation_id,
                        search_id: searchId,
                        reason,
                      },
                    );
                    onSelected?.(updated);
                    onClose();
                  }, "Price snapshot selected")
                }
              >
                Confirm and recalculate
              </button>
              <button
                className="button light"
                onClick={() => setConfirm(undefined)}
              >
                Cancel
              </button>
            </div>
          </section>
        )}
      </div>
    </Modal>
  );
}
