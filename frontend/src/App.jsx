import React, { useState, useRef } from 'react';
import Markdown from 'react-markdown'

function App() {
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [messageDetails, setMessageDetails] = useState("");
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  async function chat(message) {
    const response = await fetch("http://127.0.0.1:8000", {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    })

    const body = await response.json();
    setMessages(body.messages);
  }

  const sendMessage = async (e) => {
    e.preventDefault();

    if (!inputMessage.trim()) return;

    const receivedText = await chat(inputMessage);

    setInputMessage('');
  };

  const openModal = (message) => {
    setSelectedMessage(message);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedMessage(null);
  };

  const textareaRef = useRef(null);

  const defaultQuiz = `{
  "title": ""
}
  `;

  return (
    <div className="max-w-4xl mx-auto py-16 px-4 max-h-screen overflow-y-auto mb-48">
      <div className="fixed top-18 left-18 w-128">
        <textarea
          ref={textareaRef}
          rows={40}
          className="w-full py-3 px-6 border border-gray-200 font-mono text-sm bg-gray-50"
          defaultValue={defaultQuiz}
        />
      </div>
      <div>
        {messages.map((message, index) => {
          switch (message.type) {
            case 'human':
              return (
                <div key={index} className="text-right">
                  <span className="inline-block bg-gray-100 px-6 py-3 rounded-full whitespace-pre-wrap">
                    {message.content}
                  </span>
                </div>
              )
            default:
              return (
                <div key={index}>
                  <div className="flex gap-2">
                    <div
                      className="bg-gray-900 text-white text-sm px-3 py-1 rounded-full uppercase cursor-pointer hover:bg-gray-700 transition-colors"
                      onClick={() => openModal(message)}
                    >
                      {message.type}
                    </div>

                    <div className="bg-gray-900 text-white text-sm px-3 py-1 rounded-full">
                      {`Tool calls: ${message.tool_calls?.length}`}
                    </div>
                  </div>
                  <div className="mt-8 prose">
                    <Markdown>{message.content}</Markdown>
                  </div>
                </div>
              )
          }
        })}
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

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 flex backdrop-blur-sm items-center justify-center z-50" onClick={closeModal}>
          <pre className="bg-gray-100 m-28 p-4 rounded-lg overflow-auto text-sm">
            {JSON.stringify(selectedMessage, null, 2)}
          </pre>
        </div>
      )}

    </div>
  );
}

export default App;
