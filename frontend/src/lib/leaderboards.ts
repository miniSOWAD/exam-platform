export type LeaderboardRow = { rank: number; student: string; score: number; max_score: number | null; accuracy: number | null };
export type LeaderboardCatalog = { exams: { id: string; title: string; subject: string }[]; papers: string[]; subjects: string[] };
export type LeaderboardScope = 'exam' | 'paper' | 'subject';
