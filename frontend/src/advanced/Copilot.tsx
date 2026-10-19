import { useState } from "react";
import { post } from "../api";
import { Panel } from "../ui";
import { Field, Facts, useAction } from "./shared";
type Answer = {
  answer: string;
  facts: Record<string, unknown>;
  sources: {
    selection_id?: number;
    url?: string | null;
    source_type: string;
  }[];
  tools: string[];
  explanation_source: string;
  audit_event_id: number;
};
export function EstimateCopilot({
  projectId,
  estimateId,
}: {
  projectId: number;
  estimateId: number;
}) {
  const action = useAction(),
    [question, setQuestion] = useState(
      "What is this estimate’s budget impact?",
    ),
    [answer, setAnswer] = useState<Answer>();
  return (
    <Panel
      title="Estimating copilot"
      subtitle="Answers use persisted records and deterministic tools. No approval or payment authority."
    >
      <form
        className="advanced-form"
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(async () => {
            setAnswer(
              await post<Answer>("/advanced/ask", {
                project_id: projectId,
                estimate_id: estimateId,
                question,
              }),
            );
          }, "Analysis recorded");
        }}
      >
        <Field label="Ask about this estimate">
          <input
            required
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </Field>
        <div className="advanced-inline">
          {[
            "What is the budget impact?",
            "What happens if steel prices increase 10%?",
            "What is the cash-flow forecast?",
          ].map((q) => (
            <button
              type="button"
              key={q}
              className="button light"
              onClick={() => setQuestion(q)}
            >
              {q}
            </button>
          ))}
        </div>
        <button className="button primary" disabled={action.busy}>
          Analyze estimate
        </button>
        {action.feedback}
        {answer && (
          <div className="copilot-answer">
            <p>{answer.answer}</p>
            <span className="eyebrow">
              {answer.explanation_source} · audit event #{answer.audit_event_id}
            </span>
            <div className="advanced-inline">
              {answer.sources.map((s, i) =>
                s.url ? (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View {s.source_type.toLowerCase()} source
                  </a>
                ) : (
                  <span key={i}>
                    Internal evidence selection #{s.selection_id} ·{" "}
                    {s.source_type}
                  </span>
                ),
              )}
            </div>
            <details>
              <summary>Tools, calculation and evidence</summary>
              <Facts data={{ tools: answer.tools, ...answer.facts }} />
            </details>
          </div>
        )}
      </form>
    </Panel>
  );
}
