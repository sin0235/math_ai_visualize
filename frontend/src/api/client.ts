import type { RenderResponse } from '../types/scene';

export async function renderProblem(problemText: string, preferredAiProvider?: string): Promise<RenderResponse> {
  const response = await fetch('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ problem_text: problemText, preferred_ai_provider: preferredAiProvider }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Không thể dựng hình từ đề bài.');
  }

  return response.json();
}
