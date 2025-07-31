import { useEffect, useState } from "react";

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

function uiPropMessageReducer(messages, propMessage) {
  const message = messages.find(m => m.id === propMessage.id);

  if (message) {
    message.props[propMessage.prop] += propMessage.value;
  } else {
    console.log("UI Prop message received without corresponding UI message:", propMessage);
  }

  return messages;
}

export function useStream(options) {
  const [values, setValues] = useState({});

  const client = new Client({ apiUrl: options.apiUrl, threadId: options.threadId });

  useEffect(() => {
    async function fetchThread() {
      const thread = await client.threads.get(options.threadId);
      setValues(thread);
    }
    fetchThread();
  }, [options.threadId]);

  const submit = async (input) => {
    if (input.message) {
      setValues(values => ({ ...values, messages: [...values.messages, { id: Date.now(), type: "HumanMessage", content: input.message }] }));
    }

    const stream = client.runs.stream(input);

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

      if (data.type === "UIPropMessageChunk") {
        setValues(values => {
          const ui = uiPropMessageReducer(values.ui, data);

          return { ...values, ui };
        });
      }

      if (data.type === "values") {
        setValues(data.values);
      }
    }
  }

  return {
    submit,
    get values() {
      return values;
    },
    get messages() {
      return values.messages || [];
    },
  }
}
