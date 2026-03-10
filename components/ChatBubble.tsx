interface ChatBubbleProps {
  content: string
  isMine: boolean
  time: string
}

export default function ChatBubble({ content, isMine, time }: ChatBubbleProps) {
  return (
    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[75%] px-4 py-2.5 rounded-2xl ${
          isMine
            ? 'bg-amber-500 text-white rounded-br-md'
            : 'bg-gray-100 text-gray-800 rounded-bl-md'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
        <p className={`text-[10px] mt-1 ${isMine ? 'text-amber-100' : 'text-gray-400'}`}>
          {time}
        </p>
      </div>
    </div>
  )
}
