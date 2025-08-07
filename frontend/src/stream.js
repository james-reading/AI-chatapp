import { useState, useEffect } from "react";

import { Client } from "./client.js";

function messageReducer(messages, newMessage) {
  const message = messages.find(m => m.id === newMessage.id);

  if (message) {
    message.content += newMessage.content;
  } else {
    messages.push({
      id: newMessage.id,
      type: "AIMessage",
      content: newMessage.content,
    });
  }
  return messages;
}

function uiMessageReducer(messages, newMessage) {
  const message = messages.find(m => m.id === newMessage.id);

  if (message) {
    message.props = { ...message.props, ...newMessage.props };
  } else {
    messages.push({
      id: newMessage.id,
      type: "UIMessage",
      name: newMessage.name,
      props: newMessage.props,
      metadata: newMessage.metadata,
    });
  }
  return messages;
}

function getAuthToken() {
  let token = localStorage.getItem("ais:token");

  if (!token) {
    token = prompt("Enter your auth token");

    if (token) {
      localStorage.setItem("ais:token", token);
    }
  }

  return token;
}

export function useStream(options) {
  const [values, setValues] = useState({
    messages: [],
    ui: [],
  });

  const token = getAuthToken();
  const threadId = localStorage.getItem("ais:threadId");
  const client = new Client({ apiUrl: options.apiUrl, token: token });

  useEffect(() => {
    if (threadId) {
      client.threads.get(threadId).then(thread => {
        if (thread.values) {
          setValues(thread.values)
        }
      });
    }
  }, [threadId]);

  const ensureThread = async () => {
    if (!threadId) {
      const thread = await client.threads.create();

      localStorage.setItem("ais:threadId", thread.threadId);
      return thread.threadId;
    }
    return threadId;
  };

  const reset = () => {
    localStorage.removeItem("ais:threadId");
    setValues({
      messages: [],
      ui: [],
    });
  };

  const submit = async (input) => {
    const currentThreadId = await ensureThread();

    if (input.message) {
      setValues(values => {
        let messages = values.messages;

        messages.push({
          id: crypto.randomUUID(),
          type: "HumanMessage",
          content: input.message
        })

        return { ...values, messages };
      })

      setTimeout(() => options.onNewHumanMessage(), 0);
    }

    const stream = client.runs.stream(currentThreadId, options.assistantId, input);

    for await (const data of stream) {
      if (data.type === "AIMessageChunk") {
        setValues(values => {
          const messages = messageReducer(values.messages, data);

          return { ...values, messages };
        });
      }

      if (data.type === "UIMessageChunk") {
        setValues(values => {
          const ui = uiMessageReducer(values.ui, data);

          return { ...values, ui };
        });
      }
    }
  }

  return {
    submit,
    reset,
    get values() {
      return values;
    },
    get messages() {
      return values.messages || [];
    },
    get threadId() {
      return threadId;
    },
  }
}
