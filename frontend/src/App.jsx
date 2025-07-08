import React, { useState, useRef } from 'react';
import Markdown from 'react-markdown'

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [streamedText, setStreamedText] = useState('');

  async function chat(message) {
    const response = await fetch("http://127.0.0.1:8000", {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    })

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
    let thinkingText = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        console.log('Stream finished');
        break;
      };

      value.split('\n').forEach((line) => {
        if (line.trim() && line.startsWith('data: ')) {
          const jsonData = line.substring(6); // Remove 'data: ' prefix
          const parsed = JSON.parse(jsonData);

          // Thinking messages need to be streamed to the chat area
          if (parsed.type === 'thinking') {
            thinkingText += parsed.content;
            setStreamedText(thinkingText);
          } else if (parsed.type === 'question') {
            // Question messages contain the JSON of the final question
            if (textareaRef.current) {
              textareaRef.current.value = JSON.stringify(parsed.content, null, 2);
            }
          }
        }
      });
    }

    return thinkingText;
  }

  const sendMessage = async (e) => {
    e.preventDefault();

    if (!inputMessage.trim()) return;

    // Add the sent message to the chat
    setMessages([...messages, { text: inputMessage, type: "sent" }]);

    const message = inputMessage
    // Clear the input message
    setInputMessage('');

    // Clear the textarea
    if (textareaRef.current) textareaRef.current.value = '';

    const receivedText = await chat(message);

    // Clear the streamed text after receiving the final response
    setStreamedText('');

    // Add the final response to the chat
    setMessages((prevMessages) => [
      ...prevMessages,
      { text: receivedText, type: "received" }
    ]);
  };

  const textareaRef = useRef(null);

  return (
    <div className="max-w-4xl mx-auto py-16 px-4 max-h-screen overflow-y-auto mb-48">
      {/* <div className="fixed top-18 left-18 w-128">
        <textarea
          ref={textareaRef}
          readOnly
          placeholder="Generated question will appear here..."
          rows={40}
          className="w-full py-3 px-6 border border-gray-200 font-mono text-sm bg-gray-50"
        />
      </div> */}
      <div>
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
      </div>
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
