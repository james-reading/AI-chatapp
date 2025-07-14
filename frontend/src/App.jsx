import React, { useState, useRef } from 'react';
import Markdown from 'react-markdown'

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [streamedText, setStreamedText] = useState('');
  const [requirements, setRequirements] = useState({
    topic: '',
    target_persona: '',
    difficulty_level: '',
  });
  const [briefing, setBriefing] = useState('');
  const [questions, setQuestions] = useState([

  ]);

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
          } else if (parsed.type === 'tool') {
            parsed.content.forEach((tool) => {

              switch (tool.name) {
                case 'set_lab_requirements':
                  setRequirements(tool.args.requirements || {});
                  break;
                case 'set_briefing':
                  setBriefing(tool.args.briefing || "");
                  break;
                case 'create_question':
                  setQuestions((prevQuestions) => {
                    const existingQuestion = prevQuestions.find(q => q.id === tool.id);
                    if (existingQuestion) {
                      // Update existing question
                      return prevQuestions.map(q => q.id === tool.id ? { ...q, ...tool.args.question } : q);
                    } else {
                      // Add new question
                      return [...prevQuestions, { id: tool.id, ...tool.args.question }];
                    }
                  });
                  break;
              }
            });
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
    <div className="container mx-auto py-16 px-4 max-h-screen overflow-y-auto mb-48 grid grid-cols-2 gap-8">
      <div className="bg-gray-50 border-gray-100 p-6">
        <div>
          <span className="font-bold">Topic: </span>
          <span>{requirements.topic}</span>
        </div>
        <div>
          <span className="font-bold">Target Persona: </span>
          <span>{requirements.target_persona}</span>
        </div>
        <div>
          <span className="font-bold">Difficulty: </span>
          <span>{requirements.difficulty_level}</span>
        </div>

        <div className="mt-8">
          <h2 className="text-lg font-bold">Briefing</h2>
          <div className="mt-4 prose">
            <Markdown>{briefing}</Markdown>
          </div>
        </div>

        <div>
          <h2 className="text-lg font-bold mt-8">Questions</h2>
          <div className="mt-4">
            {questions && questions.map((question, index) => {
              return (
                <div key={index} className="mb-4 p-3 bg-white rounded-lg">
                  <div className="">{question.title}</div>
                  <ul className="list-disc text-sm pl-8">
                    {question.options && question.options.map((option, optionIndex) => {
                      return (
                        <li key={optionIndex} className="">
                          {option.value}
                          {question.correct_option === optionIndex && (
                            <span className="text-green-500 ml-2">(Correct)</span>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )
            })}
          </div>
        </div>
      </div>
      <div className="">
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
