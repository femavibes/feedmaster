export interface TopPostCard {
  type: 'post_card';
  uri: string;
  text: string;
  author: string;
  avatar: string;
  created_at: string;
  like_count: number;
  repost_count: number;
  reply_count: number;
  quote_count: number;
  post_url: string;
}

export interface TopLinkCard {
  type: 'link_card';
  uri: string;
  title: string;
  description: string;
  image: string;
  url: string;
  count?: number;
}

export interface TopUser {
  type: 'user';
  did: string;
  handle: string;
  display_name?: string;
  avatar_url?: string;
  count: number;
}

export interface TopHashtag {
  type: 'hashtag';
  hashtag: string;
  count: number;
}

export interface TopDomain {
  type: 'domain';
  domain: string;
  count: number;
}

export interface TopGeoItem {
  type: 'geo';
  region?: string;
  city?: string;
  country?: string;
  count: number;
}

export interface TopLink {
  type: 'link';
  uri: string;
  count: number;
}

export type TopItem = TopPostCard | TopLinkCard | TopUser | TopHashtag | TopDomain | TopGeoItem | TopLink;

export interface AggregateData {
  hashtags?: TopHashtag[];
  posters?: TopUser[];
  links?: TopLinkCard[];
  streaks?: any[]; // Define a proper type for streaks if you have one
  top?: TopItem[];
  news_cards?: TopLinkCard[];
  cards?: TopLinkCard[];
}

export interface Aggregates {
  top_hashtags: TopHashtag[];
  top_users: TopUser[];
  top_posters_by_count: TopUser[];
  top_mentions: TopUser[];
  longest_streaks: any[];
  active_streaks: any[];
  top_news_links: TopLinkCard[];
  top_links: TopLink[];
  top_link_cards: TopLinkCard[];
  top_videos: TopPostCard[];
  top_images: TopPostCard[];
  top_cities: TopGeoItem[];
  top_regions: TopGeoItem[];
  top_countries: TopGeoItem[];
  first_time_posters: TopUser[];
  top_domains: TopDomain[];
}