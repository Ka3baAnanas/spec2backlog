import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { Question, Section } from "../../api/client";
import { api } from "../../api/client";
import { errorMessage } from "../../lib/errors";
import { Button } from "../Button";
import { Chip } from "../Chip";
import { useToast } from "../Toast";
import { Copy, CheckCircle } from "../Icons";

function QuestionRow({
  question,
  onSave,
  saving,
}: {
  question: Question;
  onSave: (answer: string) => void;
  saving: boolean;
}) {
  const [answer, setAnswer] = useState(question.answer);

  return (
    <div className="question-row">
      <p className="question-row__text">{question.text}</p>
      <textarea
        className="input input--area"
        placeholder="Answer for the client…"
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
      />
      <div className="question-row__foot">
        <Chip tone={question.status === "answered" ? "green" : question.status === "ignored" ? "outline" : "yellow"}>
          {question.status}
        </Chip>
        <Button
          size="sm"
          variant="secondary"
          loading={saving}
          disabled={!answer.trim()}
          onClick={() => onSave(answer.trim())}
        >
          Save answer
        </Button>
      </div>
    </div>
  );
}

export function QuestionsTab({
  projectId,
  projectName,
  questions,
  sections,
  loading,
  onRefresh,
}: {
  projectId: string;
  projectName: string;
  questions: Question[];
  sections: Section[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [savingId, setSavingId] = useState<string | null>(null);

  const sectionsById = useMemo(() => new Map(sections.map((section) => [section.id, section])), [sections]);
  const grouped = useMemo(() => {
    const map = new Map<string, Question[]>();
    for (const question of questions) {
      const bucket = map.get(question.section_id);
      if (bucket) bucket.push(question);
      else map.set(question.section_id, [question]);
    }
    return Array.from(map.entries());
  }, [questions]);

  const saveMutation = useMutation({
    mutationFn: ({ id, answer }: { id: string; answer: string }) =>
      api.patchQuestion(id, { answer, status: "answered" }),
    onMutate: ({ id }) => setSavingId(id),
    onSuccess: () => {
      toast({ tone: "success", title: "Answer saved", message: "The client answer is attached to the question." });
      void queryClient.invalidateQueries({ queryKey: ["questions", projectId] });
      onRefresh();
    },
    onError: (error) => toast({ tone: "error", title: "Could not save answer", message: errorMessage(error) }),
    onSettled: () => setSavingId(null),
  });

  const copyEmail = async () => {
    const lines: string[] = [
      `Subject: Clarifications needed — ${projectName}`,
      "",
      "Hello,",
      "",
      "We are turning the functional specification into a validated backlog. Could you clarify the following points?",
      "",
    ];
    grouped.forEach(([sectionId, items], index) => {
      const section = sectionsById.get(sectionId);
      lines.push(`${index + 1}. Section ${section?.number ?? "—"} — ${section?.title ?? "Untitled"}`);
      for (const item of items) {
        lines.push(`   • ${item.text}`);
        if (item.answer) lines.push(`     Answer: ${item.answer}`);
      }
      lines.push("");
    });
    lines.push("Thank you,");
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      toast({ tone: "success", title: "Email copied", message: "Paste it into your mail client." });
    } catch (error) {
      toast({ tone: "error", title: "Could not copy", message: errorMessage(error) });
    }
  };

  return (
    <div className="questions-tab">
      <div className="tab-head">
        <div>
          <div className="eyebrow">
            <span className="eyebrow__dot" aria-hidden="true" />
            Human gaps
          </div>
          <h2>Questions for the client</h2>
          <p>Generated questions are grouped by source section. Answer them, then copy the email.</p>
        </div>
        <Button
          variant="primary"
          icon={<Copy size={15} />}
          onClick={() => void copyEmail()}
          disabled={!questions.length}
        >
          Copy as email to client
        </Button>
      </div>

      {loading ? (
        <div className="backlog-empty card card--pad">
          <strong>Loading questions…</strong>
        </div>
      ) : !questions.length ? (
        <div className="backlog-empty card card--pad">
          <CheckCircle size={22} />
          <strong>No open questions</strong>
          <p>The generated backlog did not flag missing information for this specification.</p>
        </div>
      ) : (
        <div className="question-groups">
          {grouped.map(([sectionId, items]) => {
            const section = sectionsById.get(sectionId);
            return (
              <section key={sectionId} className="question-group card card--pad">
                <div className="question-group__head">
                  <div>
                    <span className="question-group__num">Section {section?.number || "—"}</span>
                    <h3>{section?.title || "Unknown section"}</h3>
                  </div>
                  <Chip tone="outline">{items.length} question{items.length === 1 ? "" : "s"}</Chip>
                </div>
                {items.map((question) => (
                  <QuestionRow
                    key={question.id}
                    question={question}
                    saving={savingId === question.id && saveMutation.isPending}
                    onSave={(answer) => saveMutation.mutate({ id: question.id, answer })}
                  />
                ))}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
