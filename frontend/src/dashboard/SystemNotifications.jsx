import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  CalendarClock,
  CheckCheck,
  FileClock,
  HardHat,
  Landmark,
  LoaderCircle,
  UserPlus,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import client from "@/lib/api";
import { relativeDate } from "@/lib/format";

const NOTIFICATION_REFRESH_MS = 30_000;

const KIND_ICON = {
  appointment: CalendarClock,
  new_lead: UserPlus,
  lead_sla: AlertTriangle,
  quote_waiting: FileClock,
  site_criticality: HardHat,
  payment_due: Landmark,
};

const SEVERITY_STYLE = {
  urgent: "border-red-400/30 bg-red-500/10 text-red-300",
  warning: "border-amber-400/30 bg-amber-500/10 text-amber-300",
  info: "border-brand/30 bg-brand/10 text-brand",
};

function updateReadState(payload, ids) {
  if (!payload?.items) return payload;
  const readIds = new Set(ids);
  const items = payload.items.map((item) =>
    readIds.has(item.id) ? { ...item, read: true } : item,
  );
  return {
    ...payload,
    items,
    unread_count: items.filter((item) => !item.read).length,
  };
}

export default function SystemNotifications() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const queryKey = ["system-notifications"];
  const notificationsQuery = useQuery({
    queryKey,
    queryFn: async () => (await client.get("/notifications")).data,
    refetchInterval: NOTIFICATION_REFRESH_MS,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });
  const payload = {
    ...(notificationsQuery.data || {}),
    items: Array.isArray(notificationsQuery.data?.items)
      ? notificationsQuery.data.items
      : [],
    unread_count: Number(notificationsQuery.data?.unread_count || 0),
  };
  const unreadCount = Number(payload.unread_count || 0);

  const markRead = useMutation({
    mutationFn: async (notificationId) =>
      client.post(`/notifications/${notificationId}/read`),
    onMutate: async (notificationId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (current) =>
        updateReadState(current, [notificationId]),
      );
      return { previous };
    },
    onError: (_error, _notificationId, context) => {
      if (context?.previous)
        queryClient.setQueryData(queryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const markAllRead = useMutation({
    mutationFn: async () => client.post("/notifications/read-all"),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      const ids = previous?.items?.map((item) => item.id) || [];
      queryClient.setQueryData(queryKey, (current) =>
        updateReadState(current, ids),
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous)
        queryClient.setQueryData(queryKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const openNotification = (item) => {
    if (!item.read) markRead.mutate(item.id);
    navigate(item.href);
  };

  return (
    <DropdownMenu
      onOpenChange={(isOpen) => {
        if (isOpen) void notificationsQuery.refetch();
      }}
    >
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          data-testid="notifications-trigger"
          className="relative inline-flex min-h-11 min-w-11 touch-manipulation items-center justify-center rounded-xl text-fog hover:text-ink active:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          aria-label={
            unreadCount
              ? `${unreadCount} notifiche da leggere`
              : "Nessuna notifica da leggere"
          }
        >
          <Bell className="h-5 w-5" aria-hidden="true" />
          {unreadCount > 0 && (
            <span
              aria-hidden="true"
              className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[9px] text-white"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        aria-label="Centro notifiche"
        className="max-h-[min(36rem,calc(100dvh-5rem))] w-[min(24rem,calc(100vw-1rem))] overflow-y-auto border-stroke bg-surface p-0 shadow-2xl"
      >
        <DropdownMenuLabel className="flex min-h-12 items-center justify-between gap-3 px-4 py-3 text-ink">
          <span className="font-display text-xs uppercase tracking-wider">
            Notifiche
          </span>
          <span className="font-body text-[10px] font-normal text-fog">
            {unreadCount ? `${unreadCount} da leggere` : "Tutto letto"}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="m-0 bg-stroke" />

        {notificationsQuery.isLoading && (
          <div className="flex min-h-28 items-center justify-center gap-2 px-4 text-sm text-fog">
            <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
            Aggiornamento notifiche...
          </div>
        )}

        {notificationsQuery.isError && !notificationsQuery.isLoading && (
          <div className="px-4 py-6 text-center font-body text-sm text-red-300">
            Notifiche temporaneamente non disponibili.
          </div>
        )}

        {!notificationsQuery.isLoading &&
          !notificationsQuery.isError &&
          payload.items.length === 0 && (
            <div className="px-5 py-8 text-center">
              <CheckCheck
                className="mx-auto mb-2 h-6 w-6 text-brand"
                aria-hidden="true"
              />
              <p className="font-display text-xs uppercase tracking-wide text-ink">
                Nessuna azione urgente
              </p>
              <p className="mt-1 font-body text-xs text-fog">
                La campanella si aggiorna automaticamente.
              </p>
            </div>
          )}

        {!notificationsQuery.isLoading &&
          payload.items.map((item) => {
            const Icon = KIND_ICON[item.kind] || Bell;
            return (
              <DropdownMenuItem
                key={item.id}
                data-testid={`notification-${item.id}`}
                onSelect={() => openNotification(item)}
                className={`relative min-h-[4.75rem] cursor-pointer items-start gap-3 rounded-none border-b border-stroke/70 px-4 py-3 focus:bg-surface-2 focus:text-ink ${
                  item.read ? "opacity-70" : "bg-surface-2/40"
                }`}
              >
                {!item.read && (
                  <span
                    className="absolute right-3 top-3 h-2 w-2 rounded-full bg-brand"
                    aria-label="Da leggere"
                  />
                )}
                <span
                  className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
                    SEVERITY_STYLE[item.severity] || SEVERITY_STYLE.info
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1 pr-3">
                  <span className="block font-display text-[11px] uppercase tracking-wide text-ink">
                    {item.title}
                  </span>
                  <span className="mt-1 block whitespace-normal break-words font-body text-xs leading-relaxed text-fog">
                    {item.message}
                  </span>
                  <span className="mt-1 block font-body text-[10px] text-fog/80">
                    {relativeDate(item.occurred_at)}
                  </span>
                </span>
              </DropdownMenuItem>
            );
          })}

        {unreadCount > 0 && (
          <>
            <DropdownMenuSeparator className="m-0 bg-stroke" />
            <DropdownMenuItem
              data-testid="notifications-read-all"
              disabled={markAllRead.isPending}
              onSelect={(event) => {
                event.preventDefault();
                markAllRead.mutate();
              }}
              className="min-h-11 cursor-pointer justify-center rounded-none font-display text-[10px] uppercase tracking-wider text-brand focus:bg-brand/10 focus:text-brand"
            >
              {markAllRead.isPending ? (
                <LoaderCircle
                  className="h-4 w-4 animate-spin"
                  aria-hidden="true"
                />
              ) : (
                <CheckCheck className="h-4 w-4" aria-hidden="true" />
              )}
              Segna tutte come lette
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
