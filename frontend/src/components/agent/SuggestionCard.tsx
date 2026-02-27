interface Props {
  text: string;
  onClick: () => void;
}

export default function SuggestionCard({ text, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-sm text-gray-300 hover:bg-gray-800 hover:text-gray-100 hover:border-gray-600 transition-colors"
    >
      {text}
    </button>
  );
}
