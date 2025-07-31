import { useState } from "react";

import { useStream } from "./stream.js";
import Question from "./Question";


export default function App() {
  const params = new URLSearchParams(window.location.search);

  const thread = useStream({
    apiUrl: "http://localhost:8000",
    threadId: params.get("threadId") || Date.now().toString()
  });

  const [questions, setQuestions] = useState([]);

  const acceptQuestion = question => {
    setQuestions((prevQuestions) => [...prevQuestions, question]);
    thread.submit({
      command: {
        update: {
          ui: [
            {
              ...question,
              props: {
                ...question.props,
                accepted: true
              }
            }
          ]
        }
      }
    });
  };

  const previewQuestion = thread.values.ui?.filter((ui) => ui.name === "Question" && !ui.props.accepted).at(-1);

  return (
    <div className="h-screen max-h-screen grid grid-cols-3">
      <div className="px-8">
        <div className="text-center text-2xl font-bold mt-4 mb-8">
          Lab Builder State
        </div>
        <div className="flex flex-col gap-y-4">
          {questions.map(question => (
            <Question
              key={question.id}
              props={question.props}
            />
          ))}
        </div>
      </div>
      <div className="px-8 border-l border-r border-gray-400">
        <div className="text-center text-2xl font-bold mt-4 mb-8">
          UI Previews
        </div>
        {previewQuestion && (
          <Question
            key={previewQuestion.id}
            props={previewQuestion.props}
            onAccept={() => acceptQuestion(previewQuestion)}
          />
        )}
      </div>
      <div className="px-8 flex flex-col" >
        <div className="text-center text-2xl font-bold mt-4 mb-8">
          Chat
        </div>
        <div className="grow overflow-y-auto">
          {thread.messages.map((message,) => (
            <div key={message.id}>
              {message.type === "HumanMessage" ? (
                <div className="text-right mb-8">
                  <span className="inline-block bg-gray-200 px-6 py-3 rounded-full">{message.content}</span>
                </div>
              ) : (
                <div className="mb-8">
                  <div>{message.content}</div>
                  {thread.values.ui?.filter((ui) => ui.metadata?.message_id === message.id).map((ui) => {
                    switch (ui.name) {
                      case "Question":
                        return (
                          <div key={ui.id} className="border p-5 rounded-xl border-gray-300 bg-gray-50 flex justify-between">
                            <div>Created Question</div>
                            {ui.props.accepted && (
                              <div className="font-bold">Accepted</div>
                            )}
                          </div>
                        );
                      default:
                        return JSON.stringify(ui, null, 2);
                    }
                  })}
                </div>
              )}
            </div>
          ))}
        </div>

        <form className="flex gap-x-4 mb-16"
          onSubmit={(e) => {
            e.preventDefault();

            const form = e.target
            const message = new FormData(form).get("message");

            form.reset();
            thread.submit({ message });
          }}
        >
          <input
            type="text"
            placeholder="Type your message here..."
            name="message"
            className="w-full py-3 px-6 border border-gray-200 rounded-full"
          />

          <button className="cursor-pointer bg-gray-100 py-3 px-6 rounded-full" type="submit">Send</button>
        </form>
      </div>
    </div>
  );
}
