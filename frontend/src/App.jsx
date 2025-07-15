import React, { useState, useRef } from 'react';
import Markdown from 'react-markdown';

function App() {
  const threadId = useRef(); // Generate a unique thread ID
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [streamedText, setStreamedText] = useState('');

  async function chat(message) {
    const response = await fetch("http://127.0.0.1:8000", {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message, thread_id: threadId.current.value })
    })

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()

    let finalText = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      value.split('\n').forEach(line => {
        line = line.trim();
        if (!line) return;

        const data = JSON.parse(line);

        if (data.type === 'stream') {
          finalText += data.token;
          setStreamedText(finalText);
        }
      });
    }

    return finalText;
  }

  const sendMessage = async (e) => {
    e.preventDefault();

    const currentMessage = inputMessage.trim();
    if (!currentMessage) return;

    // Add the sent message to the chat
    setMessages([...messages, { text: currentMessage, type: "sent" }]);
    setInputMessage('');

    const finalText = await chat(currentMessage);

    setStreamedText('');
    setMessages(prevMessages => [
      ...prevMessages,
      { text: finalText, type: "received" }
    ]);

  };

  return (
    <div className="max-w-5xl mx-auto py-16 px-4 max-h-screen overflow-y-auto mb-48">
      <div className="flex justify-center text xs text-gray-500 mb-8">
        <span className="mr-2">Thread ID:</span>
        <input ref={threadId} type="text" defaultValue={Date.now().toString()} />
      </div>
      {messages.map((message, index) => {
        return message.type === "received" ? (
          <div key={index} className="mt-8 prose">
            <Markdown>{message.text}</Markdown>
          </div>
        ) : (
          <div key={index} className="text-right">
            <span className="inline-block bg-gray-100 px-6 py-3 rounded-full whitespace-pre-wrap">
              {message.text}
            </span>
          </div>
        )
      })}
      {streamedText !== '' && (
        <div className="mt-8 prose">
          <Markdown>{streamedText}</Markdown>
        </div>
      )}
      <form
        onSubmit={sendMessage}
        className="max-w-4xl mx-auto p-4 flex gap-x-4 fixed bottom-0 left-0 right-0 mb-24">
        <input
          type="text"
          placeholder="Type your message here..."
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          className="w-full py-3 px-6 border border-gray-200 rounded-full"
        />
        <button className="cursor-pointer bg-gray-100 py-3 px-6 rounded-full">
          Send
        </button>
      </form>
    </div>
  );
}

export default App;
