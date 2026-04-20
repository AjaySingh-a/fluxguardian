import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center justify-center gap-4 px-6 py-32 text-center">
      <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
        404
      </span>
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        That route doesn't exist yet. Head back to the overview.
      </p>
      <Button asChild size="sm">
        <Link to="/">Return home</Link>
      </Button>
    </div>
  );
}
