import { IzinDurum, DURUM_LABELS, DURUM_COLORS } from "@/types/leave";

interface Props {
  durum: IzinDurum;
  className?: string;
}

export default function LeaveStatusBadge({ durum, className = "" }: Props) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${DURUM_COLORS[durum]} ${className}`}
    >
      {DURUM_LABELS[durum]}
    </span>
  );
}
