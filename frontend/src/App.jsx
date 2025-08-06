import { useState } from "react";

import Question from "./Question";
import Thread from "./Thread";

export default function App() {
  const params = new URLSearchParams(window.location.search);

  const [lab, setLab] = useState({
    topic: "Maths",
    questions: []
  });

  const [threadId, setThreadId] = useState(params.get("threadId"));

  const [previewItem, setPreviewItem] = useState(null);

  const acceptQuestion = (question) => {
    setLab((prevLab) => {
      return { ...prevLab, questions: [...prevLab.questions, question.props] };
    });
    setPreviewItem(null);
  };

  return (
    <div className="h-screen max-h-screen grid grid-cols-3">
      <div className="px-8">
        <div className="text-center text-2xl font-bold mt-4 mb-8">
          Lab Builder State
        </div>
        <textarea
          className="w-full h-full outline-none"
          value={JSON.stringify(lab, null, 2)}
          onChange={(e) => {
            try {
              const newLab = JSON.parse(e.target.value);
              setLab(newLab);
            } catch (error) {
              console.error("Invalid JSON input:", error);
            }
          }}
        />
      </div>
      <div className="px-8 border-l border-r border-gray-400">
        <div className="text-center text-2xl font-bold mt-4 mb-8">
          UI Previews
        </div>
        {previewItem && (
          <Question
            key={previewItem.id}
            props={previewItem.props}
            onAccept={() => acceptQuestion(previewItem)}
            onCancel={() => setPreviewItem(null)}
          />
        )}
      </div>
      <div className="px-8 flex flex-col" >
        <div className="flex items-center justify-between mt-4 mb-8">
          <div className="text-center text-2xl font-bold ">
            Chat
          </div>
          <button
            className="cursor-pointer py-2 px-4 inline text-sm border border-gray-300 rounded-full mb-4"
            onClick={() => {
              setThreadId(Date.now().toString());
              setPreviewItem(null);
            }}>
            + New Thread
          </button>
        </div>
        {threadId && (
          <Thread
            key={threadId}
            threadId={threadId}
            lab={lab}
            onUIEvent={(ui) => {
              if (ui.name === "Question") {
                setPreviewItem(ui);
              }
            }}
          />
        )}
      </div>
    </div>
  );
}
