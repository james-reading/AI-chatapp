import { useEffect, useRef } from "react";

import { useStream, } from "./stream.js";
import Message from "./Message.jsx";

export default function Chat() {
  const scrollableContainer = useRef();
  const messagesContainer = useRef();

  const thread = useStream({
    apiUrl: "http://localhost:3004",
    assistantId: "simple_chat",
    onNewHumanMessage: () => {
      const lastMessage = messagesContainer.current.lastElementChild;
      scrollableContainer.current.scrollTo({ top: lastMessage.offsetTop, behavior: 'smooth' });
    }
  });

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollableContainer} className="grow overflow-y-auto mt-8 -mb-4">
        <div ref={messagesContainer} className="messages-container max-w-3xl mx-auto flex flex-col gap-y-8 px-4 mb-16">
          {thread.messages.map(message => (
            <Message key={message.id} thread={thread} message={message} />
          ))}
        </div>
      </div>

      <div className="w-full max-w-3xl mx-auto px-4 mb-12">
        <form className=""
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
            className="w-full py-3 px-6 z-10 bg-white border border-gray-400 shadow-sm rounded-full outline-none"
          />
        </form>
        <div className="flex justify-center gap-x-2 mt-4">
          <button
            className="cursor-pointer py-2 px-3 text-xs bg-white border border-gray-400 shadow-sm rounded-full"
            onClick={() => thread.reset()}
          >
            Reset Chat
          </button>
        </div>
      </div>
    </div >
  )
}
