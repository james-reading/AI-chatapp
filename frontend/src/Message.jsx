import { useState } from "react";

import Markdown from "react-markdown";

function HumanMessage({ content }) {
  return (
    <div className="flex items-start justify-end">
      <div className="bg-gray-100 px-6 py-3 rounded-full">{content}</div>
    </div>
  );
}

function UIMessage({ ui }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <button
      onClick={() => setIsOpen(!isOpen)}
      className="cursor-pointer w-full border border-gray-300 rounded-lg p-4">
      <div className="flex justify-between items-center">
        <div>
          {ui.name}
        </div>
        <div className="text-xs text-gray-500">
          Bytes:
          <span className="ml-1">
            {new Blob([JSON.stringify(ui)]).size}
          </span>
        </div>
      </div>

      {isOpen && (
        <div className="mt-8 text-left">
          <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(ui, null, 2)}</pre>
        </div>
      )}
    </button>
  );
}

function AIMessage({ thread, message }) {
  const uiMessages = thread.values.ui?.filter(ui => ui.metadata?.messageId === message.id);

  return (
    <div>
      <div className="prose !max-w-none"><Markdown>{message.content}</Markdown></div>
      {uiMessages.map(ui => <UIMessage key={ui.id} ui={ui} />)}
    </div >
  );
}

export default function Message({ thread, message }) {
  return (
    <div className="last-of-type:h-[calc(100dvh-250px)]">
      {message.type === "HumanMessage" ? (
        <HumanMessage content={message.content} />
      ) : (
        <AIMessage thread={thread} message={message} />
      )}
    </div>
  );
}
