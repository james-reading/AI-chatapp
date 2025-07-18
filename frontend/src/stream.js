import { useEffect, useState } from "react";

import { Client } from "./client.js";

function messageReducer(state, event) {
  const message = state.find((message) => message.id === event.id);

  if (message) {
    message.content += event.content;
  } else {
    state.push(event);
  }
  return state;
}

function uiMessageReducer(state, event) {
  const index = state.findIndex((ui) => ui.id === event.id);

  let processedEvent;
  if (index !== -1) {
    processedEvent = event.metadata.merge
      ? { ...event, props: { ...state[index].props, ...event.props } }
      : event;
    state[index] = processedEvent;
  } else {
    processedEvent = event;
    state.push(processedEvent);
  }
  return { state, processedEvent };
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
    const stream = client.runs.stream(input);

    for await (const { event, data } of stream) {
      if (event === "values") {
        setValues(data);
      }
      if (event === "custom") {
        switch (data.type) {
          case "ui":
            setValues(values => {
              const { state: ui, processedEvent } = uiMessageReducer(values.ui ?? [], data);

              if (options.onUIEvent) {
                options.onUIEvent(processedEvent);
              }

              return { ...values, ui };
            });

            break;
          default:
            console.warn("Unknown custom event type:", data.type);
        }
      }
      if (event === "messages") {
        const [message] = data;

        setValues(values => {
          const messages = messageReducer(values.messages ?? [], message);

          return { ...values, messages };
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
