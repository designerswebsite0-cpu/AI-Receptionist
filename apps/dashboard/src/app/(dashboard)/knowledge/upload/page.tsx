import { SourceUploadForm } from "@/components/source-upload-form";

export default function UploadSourcePage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-lg font-semibold text-charcoal">Upload a Knowledge Source</h1>
      <SourceUploadForm />
    </div>
  );
}
