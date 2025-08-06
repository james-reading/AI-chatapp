import { useState } from "react";

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
  let message = messages.find(m => m.id === newMessage.id);

  if (message) {
    message.props = { ...message.props, ...newMessage.props };
  } else {
    message = {
      id: newMessage.id,
      type: "UIMessage",
      name: newMessage.name,
      props: newMessage.props,
      metadata: newMessage.metadata,
    }
    messages.push(message);
  }
  return [message, messages];
}

export function useStream(options) {
  const [values, setValues] = useState({
    messages: [],
    ui: [],
    lab: {}
  });

  const client = new Client({ apiUrl: options.apiUrl, threadId: options.threadId });

  const submit = async (input) => {
    if (input.message) {
      setValues(values => {
        let messages = values.messages;

        messages.push({
          id: Date.now(),
          type: "HumanMessage",
          content: input.message
        })

        return { ...values, messages };
      })
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
          const [uiEvent, ui] = uiMessageReducer(values.ui, data);

          if (options.onUIEvent) {
            options.onUIEvent(uiEvent);
          }

          return { ...values, ui };
        });
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
