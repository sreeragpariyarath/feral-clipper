import { NewJobForm } from "@/components/jobs/NewJobForm";
import { PageHeader } from "@/components/ui/PageHeader";
import { PAGES } from "@/lib/pages";

export default function NewJobPage() {
  return (
    <div className="max-w-2xl">
      <PageHeader {...PAGES.newJob} />
      <NewJobForm />
    </div>
  );
}
