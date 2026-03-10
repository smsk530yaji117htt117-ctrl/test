interface TagBadgeProps {
  name: string
  selected?: boolean
  onClick?: () => void
}

export default function TagBadge({ name, selected, onClick }: TagBadgeProps) {
  const base = 'inline-flex items-center px-3 py-1 rounded-full text-sm transition-colors'
  const style = selected
    ? 'bg-amber-100 text-amber-700 border border-amber-300'
    : 'bg-gray-100 text-gray-600 border border-gray-200'
  const clickable = onClick ? 'cursor-pointer hover:opacity-80' : ''

  return (
    <span className={`${base} ${style} ${clickable}`} onClick={onClick}>
      {name}
    </span>
  )
}
