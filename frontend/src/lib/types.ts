export interface SeriesSummary {
  id: string; slug: string; title: string; synopsis: string; language: string;
  poster_url: string; banner_url: string; free_episode_count: number;
  is_featured: boolean; view_count: number; genres: string[]; episode_count: number;
}
export interface EpisodeSummary {
  id: string; episode_number: number; title: string; duration_seconds: number;
  thumbnail_url: string; is_free: boolean; locked: boolean;
}
export interface SeriesDetail extends SeriesSummary { episodes: EpisodeSummary[] }
export interface GenreOut { slug: string; name: string }
export interface ContinueItem {
  series: SeriesSummary; episode_number: number; episode_id: string; position_seconds: number;
}
export interface HomeData {
  featured: SeriesSummary[]; trending: SeriesSummary[]; new_releases: SeriesSummary[];
  genre_rails: { genre: GenreOut; series: SeriesSummary[] }[];
  continue_watching: ContinueItem[];
}
export interface User { id: string; email: string; name: string }
export interface Plan { id: number; name: string; price_inr: number; interval: string }
export interface CurrentSubscription {
  status: string; plan: Plan; current_period_end: string | null;
}
export interface PlaybackInfo {
  url: string; episode_id: string; episode_number: number;
  series_slug: string; resume_position: number;
}
