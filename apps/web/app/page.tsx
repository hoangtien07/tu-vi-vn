import { BirthForm } from "../features/chart/components/BirthForm";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center p-8">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight">
            Tử Vi Việt Nam
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Lập lá số Tử Vi Đẩu Số — mọi luận giải đều kèm căn cứ kiểm chứng.
          </p>
        </div>
        <BirthForm />
        <p className="text-center text-xs text-zinc-400">
          Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
        </p>
      </div>
    </main>
  );
}
