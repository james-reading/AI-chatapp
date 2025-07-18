import { useStream } from "./stream.js";

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const thread = useStream({
    apiUrl: "http://localhost:8000",
    threadId: params.get("threadId") || Date.now().toString()
  });

  const lastJoke = thread.values.ui?.find(ui => ui.name === "joke");

  return (
    <div className="max-w-4xl mx-auto px-8 bg-white">
      {lastJoke && (
        <div className="fixed top-0 left-0 bg-white m-8 p-4 whitespace-pre-wrap max-w-xl">
          <div className="text-lg font-bold mb-2">Current Joke</div>
          {JSON.stringify(lastJoke, null, 2)}
        </div>
      )}
      <div className="h-screen max-h-screen flex flex-col" >
        <div className="grow overflow-y-auto mt-16">
          {thread.messages.map((message) => (
            <div key={message.id}>
              {message.type === "human" ? (
                <div className="text-right mb-8">
                  <span className="inline-block bg-gray-100 px-6 py-3 rounded-full">{message.content}</span>
                </div>
              ) : (
                <div className="mb-8">
                  <div>{message.content}</div>
                  {thread.values.ui?.filter((ui) => ui.metadata?.message_id === message.id).map((ui) => {
                    switch (ui.name) {
                      case "web_search":
                        return (
                          <div key={ui.id} className="">
                            <span className="inline-block bg-gray-900 text-white px-4 py-2 rounded-full">
                              Web Search: {ui.props.query}
                            </span>
                            {ui.metadata?.complete && (
                              <span className="ml-2">Done!</span>
                            )}
                          </div>
                        );
                      case "joke":
                        return (
                          <div key={ui.id} className="">
                            <span className="inline-block bg-gray-900 text-white px-4 py-2 rounded-full">
                              {ui.metadata?.complete ? "Joke told ✅" : "Telling a joke..."}
                            </span>
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
