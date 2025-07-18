export class Client {
  constructor({ apiUrl, threadId }) {
    this.apiUrl = apiUrl;
    this.threadId = threadId
    this.threads = new ThreadsAPI(apiUrl);
    this.runs = new RunsAPI(apiUrl, threadId);
  }
}

class ThreadsAPI {
  constructor(apiUrl) {
    this.apiUrl = apiUrl;
  }

  async get(threadId) {
    const response = await fetch(`${this.apiUrl}/thread/${threadId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`Failed to get thread: ${response.statusText}`);
    }

    return await response.json();
  }

  async create() {
    const response = await fetch(`${this.apiUrl}/threads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: "{}",
    });

    if (!response.ok) {
      throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    return await response.json();
  }
}

class RunsAPI {
  constructor(apiUrl, threadId) {
    this.apiUrl = apiUrl;
    this.threadId = threadId;
  }

  stream(input) {
    return new StreamIterator(this.apiUrl, this.threadId, input);
  }
}

class StreamIterator {
  constructor(apiUrl, threadId, input) {
    this.apiUrl = apiUrl;
    this.threadId = threadId;
    this.input = input;
  }

  async *[Symbol.asyncIterator]() {
    const response = await fetch(`${this.apiUrl}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: this.input.message,
        thread_id: this.threadId
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to start stream: ${response.statusText}`);
    }

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      let currentEvent
      const lines = value.split('\n');
      for (const line of lines) {
        if (line.trim()) {
          const colonIndex = line.indexOf(':');

          if (colonIndex !== -1) {
            const field = line.substring(0, colonIndex).trim();
            const eventValue = line.substring(colonIndex + 1).trim();

            currentEvent ||= {};
            currentEvent[field] = field === "data" ? JSON.parse(eventValue) : eventValue;
          }
        } else {
          if (currentEvent) {
            yield currentEvent;
            currentEvent = undefined;
          }
        }
      }
    }
  }
}
