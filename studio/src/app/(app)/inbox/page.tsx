import { PageHeader } from '@/components/ui'
import { NewIdeaForm } from '@/components/new-idea-form'

export default function InboxPage() {
  return (
    <>
      <PageHeader
        title="Входящие идеи"
        description="Короткая мысль, ссылка, заметка или расшифрованный рамблинг. Обрабатывать её будем потом — сейчас важно не потерять."
      />
      <div className="max-w-2xl">
        <NewIdeaForm />
      </div>
    </>
  )
}
