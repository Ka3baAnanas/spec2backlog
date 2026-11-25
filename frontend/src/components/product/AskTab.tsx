import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { AskCitation, Section } from "../../api/client";
import { api } from "../../api/client";
import { errorMessage } from "../../lib/errors";
import { Button } from "../Button";
import { Card } from "../Card";
import { Chip } from "../Chip";
import { useToast } from "../Toast";
import { Sparkles } from "../Icons";

export function AskTab({ projectId, sections }: { projectId: string; sections: Section[] }) {
  const toast = useToast();
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState<AskCitation | null>(null);

  const askMutation = useMutation({
    mutationFn: (value: string) => api.ask(projectId, value),
    onError: (error) => toast({ tone: "error", title: "Could not answer", message: errorMessage(error) }),
  });

  const selectedSection = selected
    ? sections.find((section) => section.id === selected.section_id)
    : undefined;

  return (
    <div className="ask-tab">
      <div className="tab-head">
        <div>
          <div className="eyebrow">
            <span className="eyebrow__dot" aria-hidden="true" />
            Ask the specification
          </div>
          <h2>Ask a question, get citations</h2>
          <p>Answers are extractive and always point back to the source section.</p>
        </div>
        <Chip tone="blue">Beta</Chip>
      </div>

      <Card className="ask-card" pad>
        <form
          className="ask-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (question.trim()) askMutation.mutate(question.trim());
          }}
        >
          <textarea
            className="input input--area input--tall"
            placeholder="e.g. What happens when the transfer exceeds the daily limit?"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <div className="ask-form__actions">
            <span>{question.trim().length} characters</span>
            <Button
              variant="primary"
              type="submit"
              icon={<Sparkles size={15} />}
              loading={askMutation.isPending}
              disabled={!question.trim()}
            >
              Ask the spec
            </Button>
          </div>
        </form>
      </Card>

      {askMutation.data && (
        <Card className="ask-answer" pad>
          <div className="ask-answer__label">Answer</div>
          <p className="ask-answer__text">{askMutation.data.answer}</p>
          <div className="ask-citations">
            {askMutation.data.citations.map((citation) => (
              <button
                key={citation.section_id}
                type="button"
                className={`citation ${selected?.section_id === citation.section_id ? "is-active" : ""}`.trim()}
                onClick={() => setSelected(citation)}
              >
                <span className="citation__num">{citation.number || "§"}</span>
                <span className="citation__title">{citation.title}</span>
                <span className="citation__score">{Math.round(citation.score * 100)}%</span>
              </button>
            ))}
          </div>
        </Card>
      )}

      {selected && (
        <Card className="ask-source" pad>
          <div className="ask-source__head">
            <div>
              <span className="question-group__num">Section {selected.number || "n/a"}</span>
              <h3>{selected.title}</h3>
            </div>
            <Chip tone="outline">Citation</Chip>
          </div>
          <p className="ask-source__text">
            {selectedSection?.text || selected.snippet || "No section text available."}
          </p>
        </Card>
      )}
    </div>
  );
}
