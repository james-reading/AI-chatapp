import { useEffect } from "react";
import { useStream } from "./stream.js";

export default function Thread({ threadId, lab, onUIEvent }) {
  const thread = useStream({
    apiUrl: "http://localhost:8000",
    threadId,
    onUIEvent
  });

  useEffect(() => {
    thread.submit({ context: { lab } });
  }, [threadId]);

  return (
    <>
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
                        <button
                          key={ui.id}
                          onClick={() => setPreviewItem(ui)}
                          className="cursor-pointer inline-block block border py-3 px-4 rounded-xl border-gray-300 flex justify-between hover:bg-gray-50">
                          <span>Question</span>
                          {!ui.metadata.complete && (
                            <span className="ml-2">⌛</span>
                          )}
                        </button>
                      );
                    case "QuickActions":
                      return (
                        <div
                          key={ui.id}
                          className="flex flex-col gap-y-2 mt-2">
                          {ui.props.actions.map((action) => (
                            <button
                              key={action.label}
                              onClick={() => thread.submit({ message: action.message, context: { lab } })}
                              className="cursor-pointer inline-block block border py-3 px-4 rounded-xl border-gray-300 flex justify-between hover:bg-gray-50">
                              <span>{action.label}</span>
                            </button>
                          ))}
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
      {/* <div className="mb-4">
        <button
          onClick={() => {
            thread.submit({ message: "Create a question", context: { lab } });
          }}
          className="cursor-pointer py-2 px-4 text-sm border border-gray-300 rounded-full">Add a question ➕</button>
      </div> */}

      <form className="flex gap-x-4 mb-16"
        onSubmit={(e) => {
          e.preventDefault();

          const form = e.target
          const message = new FormData(form).get("message");

          form.reset();
          thread.submit({ message, context: { lab } });
        }}
      >
        <input
          type="text"
          placeholder="Type your message here..."
          name="message"
          className="w-full py-3 px-6 border border-gray-300 rounded-full"
        />

        <button className="cursor-pointer bg-gray-100 py-3 px-6 rounded-full" type="submit">Send</button>
      </form>
    </>
  )
}
