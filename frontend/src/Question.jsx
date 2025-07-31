export default function Question({ props, onAccept }) {
  return (
    <div className="border p-5 rounded-xl border-gray-300 bg-gray-50">
      <div className="font-bold text-lg mb-4">{props.title}</div>
      <div className="flex flex-col gap-y-2">
        {props.options?.map((option, index) => (
          <div key={index} className="border px-4 py-2 text-sm rounded-xl border-gray-300 bg-gray-50 flex justify-between">
            {option.value}
            {props.correct_option_index === index && (
              <span className="text-gray-500 text-sm">(Correct)</span>
            )}
          </div>
        ))}
      </div>
      {onAccept && (
        <div className="flex justify-end">
          <button
            className="cursor-pointer mt-5 bg-blue-500 text-white px-4 py-2 rounded-full"
            onClick={onAccept}
          >
            Accept
          </button>
        </div>
      )}
    </div>
  );
}
