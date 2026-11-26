/** Title and subtitle of each page: used by the page and by its loading skeleton, so they always match. */
export const PAGES = {
  dashboard: { title: "Dashboard", subtitle: "What's running, and what's waiting for you." },
  newJob: { title: "New job", subtitle: "Paste a Twitch VOD link or a video file path. Everything else runs on its own." },
  jobs: { title: "Jobs", subtitle: "Every download, scan and render, newest first." },
  clips: { title: "Clips", subtitle: "Watch, approve or reject, then download what you'll post." },
  streams: { title: "Streams", subtitle: "Every downloaded stream and the clips made from it" },
  posted: { title: "Posted", subtitle: "Where each clip went. Type in the views from each platform; payout uses the campaign's rate." },
  campaigns: { title: "Campaigns", subtitle: "Clipping deals: rules for the judge, payout, and end date." },
  trash: { title: "Trash", subtitle: "Clips you deleted. Their files are kept in clips_trash until you remove them by hand." },
  settings: { title: "Settings", subtitle: "Keys live in .env next to the app. Their values never reach the browser." },
} as const;
