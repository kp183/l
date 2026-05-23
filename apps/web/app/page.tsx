import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";

export default async function RootPage() {
  const { userId, getToken } = await auth();
  
  if (!userId) {
    redirect("/sign-in");
  }

  const token = await getToken();
  if (!token) {
    redirect("/sign-in");
  }

  try {
    // 1. Fetch user's organizations
    const orgs = await api.listOrgs(token);
    
    if (orgs.length === 0) {
      // No organizations -> go to onboarding step 1
      redirect("/onboarding");
    }

    // 2. Fetch projects for the first organization
    const org = orgs[0];
    const projects = await api.listProjects(org.id, token);

    if (projects.length === 0) {
      // Organization exists but no project -> go to onboarding
      redirect("/onboarding");
    }

    // 3. Project exists -> redirect to dashboard
    redirect(`/dashboard?project_id=${projects[0].id}`);
  } catch (err) {
    console.error("RootPage routing error, redirecting to onboarding:", err);
    redirect("/onboarding");
  }
}
