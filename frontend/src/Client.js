export class Client {
  constructor({ apiUrl, token }) {
    this.threads = new ThreadsAPI(apiUrl, token);
    this.runs = new RunsAPI(apiUrl, token);
  }
}

class ThreadsAPI {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
  }

  async get(threadId) {
    const response = await fetch(`${this.apiUrl}/v1/threads/${threadId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to get thread: ${response.statusText}`);
    }

    return await response.json();
  }

  async create() {
    const response = await fetch(`${this.apiUrl}/v1/threads`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    return await response.json();
  }
}

class RunsAPI {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
  }

  async *stream(threadId, assistantId, input) {
    const response = await fetch(`${this.apiUrl}/v1/threads/${threadId}/run/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      },
      body: JSON.stringify({
        assistant_id: assistantId,
        input: input
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to start stream: ${response.statusText}`);
    }

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      const lines = value.split('\n');

      for (const line of lines) {
        if (line.trim()) {
          yield JSON.parse(line);
        }
      }
    }
  }
}
