const DATE_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  month: "numeric",
  day: "numeric"
});

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("zh-CN", {
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "Asia/Shanghai"
});

export function formatDateLabel(date: string) {
  return date;
}

export function formatDateShort(value?: string) {
  if (!value) {
    return "时间未知";
  }

  return DATE_FORMATTER.format(new Date(value));
}

export function formatDateTime(value?: string) {
  if (!value) {
    return "时间未知";
  }

  return DATE_TIME_FORMATTER.format(new Date(value));
}
