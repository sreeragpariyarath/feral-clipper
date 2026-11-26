import { NewJobForm } from "@/components/jobs/NewJobForm";
import { PageHeader } from "@/components/ui/PageHeader";

export default function NewJobPage() {
  return (
    <div className="max-w-2xl">
      <PageHeader title="New job" subtitle="Paste a Twitch VOD link or a video file path. Everything else runs on its own." />
      <NewJobForm />
    </div>
  );
}
