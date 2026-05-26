import { SignUp } from "@clerk/nextjs";
import { Sparkles } from "lucide-react";

export default function SignUpPage() {
  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center bg-slate-950 overflow-hidden">
      {/* Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Brand Header */}
      <div className="relative z-10 flex items-center space-x-2 mb-8">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <Sparkles className="h-5 w-5 text-white" />
        </div>
        <span className="font-semibold text-xl tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
          AgentLens
        </span>
      </div>

      {/* Clerk Sign Up Widget */}
      <div className="relative z-10 p-2 border border-slate-900 bg-slate-900/30 rounded-2xl shadow-2xl backdrop-blur-xl">
        <SignUp
          routing="path"
          appearance={{
            variables: {
              colorPrimary: "#6366f1",
              colorBackground: "#0b0f19",
              colorText: "#f8fafc",
              colorTextSecondary: "#94a3b8",
              colorInputBackground: "#020617",
              colorInputText: "#f8fafc",
              colorBorder: "#1e293b",
            },
            elements: {
              card: "shadow-none bg-transparent",
              headerTitle: "text-slate-100",
              headerSubtitle: "text-slate-400",
              socialButtonsBlockButton: "bg-slate-950 border-slate-800 hover:bg-slate-900 text-slate-200",
              dividerLine: "bg-slate-800",
              dividerText: "text-slate-500",
              formFieldLabel: "text-slate-400 text-xs font-semibold uppercase tracking-wider",
              formInput: "bg-slate-950 border-slate-800 text-slate-100 rounded-xl focus:border-indigo-500",
              formButtonPrimary: "bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-lg shadow-indigo-600/15 py-2.5",
              footerActionLink: "text-indigo-400 hover:text-indigo-300",
            },
          }}
          signInUrl="/sign-in"
        />
      </div>
    </div>
  );
}
