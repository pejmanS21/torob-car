"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from "@/lib/account";
import { ADMIN_ERROR_TEXT, needsReauth } from "@/lib/admin";
import {
  ApiError,
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
} from "@/lib/api/client";
import type { AdminUserPage, AdminUserRow, UserRole } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import { useAppState } from "@/state/AppState";
import {
  AdminIcon,
  adminDate,
  EmptyState,
  LoadingState,
  PageHeading,
  Pagination,
  RefreshButton,
} from "../ui";
import styles from "../admin.module.css";

const PAGE_SIZE = 15;
type Action = "status" | "role" | "password" | "delete";

function actionDescription(action: Action, row: AdminUserRow, self: boolean): string {
  if (action === "delete") return "این حساب به‌همراه آگهی‌های ذخیره‌شده و هشدارهای قیمت آن حذف می‌شود. این کار قابل بازگشت نیست.";
  if (action === "role") return row.role === "admin" ? "دسترسی این حساب به پنل مدیریت برداشته می‌شود." : "این کاربر به پنل مدیریت و مدیریت حساب‌های دیگر دسترسی خواهد داشت.";
  if (action === "status") return row.is_active ? "کاربر دیگر نمی‌تواند وارد حساب خود شود. می‌توانید بعداً حساب را دوباره فعال کنید." : "دسترسی کاربر به حساب دوباره فعال می‌شود.";
  return self ? "با تغییر رمز، از حساب خارج می‌شوید و باید دوباره وارد شوید." : "نشست‌های فعلی این کاربر پایان می‌یابند و ورود بعدی با رمز جدید انجام می‌شود.";
}

async function applyUserAction(row: AdminUserRow, action: Action, password: string): Promise<void> {
  if (action === "delete") {
    await apiDelete(`/admin/users/${row.id}`);
    return;
  }
  if (action === "password") {
    await apiPost(`/admin/users/${row.id}/password`, { new: password });
    return;
  }
  const nextRole: UserRole = row.role === "admin" ? "user" : "admin";
  const patch = action === "status" ? { is_active: !row.is_active } : { role: nextRole };
  await apiPatch(`/admin/users/${row.id}`, patch);
}

const SUCCESS_MESSAGES: Record<Action, string> = {
  delete: "حساب کاربری حذف شد.",
  password: "رمز عبور بازنشانی شد.",
  status: "تغییرات حساب ذخیره شد.",
  role: "تغییرات حساب ذخیره شد.",
};

function UserActions({
  row,
  self,
  busy,
  onClose,
  onAction,
}: Readonly<{
  row: AdminUserRow;
  self: boolean;
  busy: boolean;
  onClose: () => void;
  onAction: (action: Action, password: string) => void;
}>) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [password, setPassword] = useState("");
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const titles = {
    status: row.is_active ? "غیرفعال کردن حساب" : "فعال کردن حساب",
    role: row.role === "admin" ? "تغییر نقش به کاربر" : "ارتقا به مدیر",
    password: "بازنشانی رمز عبور",
    delete: "حذف حساب کاربری",
  };
  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby="user-action-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className={styles.dialogHeading}>
        <div>
          <h2 id="user-action-title">
            {action ? titles[action] : "مدیریت حساب"}
          </h2>
          <p dir="ltr">{row.email}</p>
        </div>
        <button
          className={styles.iconButton}
          aria-label="بستن"
          disabled={busy}
          onClick={onClose}
        >
          <AdminIcon name="close" />
        </button>
      </div>
      {!action ? (
        <div className={styles.actionMenu}>
          <button disabled={self} onClick={() => setAction("status")}>
            <AdminIcon name="check" />
            <span>
              {titles.status}
              <small>
                {self
                  ? "وضعیت حساب خودتان قابل تغییر نیست"
                  : "مدیریت دسترسی کاربر به سامانه"}
              </small>
            </span>
            <AdminIcon name="arrow" size={16} />
          </button>
          <button disabled={self} onClick={() => setAction("role")}>
            <AdminIcon name="shield" />
            <span>
              {titles.role}
              <small>
                {self
                  ? "نقش حساب خودتان قابل تغییر نیست"
                  : "تغییر سطح دسترسی حساب"}
              </small>
            </span>
            <AdminIcon name="arrow" size={16} />
          </button>
          <button onClick={() => setAction("password")}>
            <AdminIcon name="settings" />
            <span>
              {titles.password}
              <small>تعیین رمز جدید و پایان نشست‌های فعال</small>
            </span>
            <AdminIcon name="arrow" size={16} />
          </button>
          <button
            className={styles.dangerText}
            disabled={self}
            onClick={() => setAction("delete")}
          >
            <AdminIcon name="close" />
            <span>
              {titles.delete}
              <small>
                {self
                  ? "حذف حساب خودتان امکان‌پذیر نیست"
                  : "حذف دائمی حساب و اطلاعات وابسته"}
              </small>
            </span>
            <AdminIcon name="arrow" size={16} />
          </button>
        </div>
      ) : (
        <form
          className={styles.actionForm}
          onSubmit={(event) => {
            event.preventDefault();
            onAction(action, password);
          }}
        >
          <p>
            {actionDescription(action, row, self)}
          </p>
          {action === "password" && (
            <label className={styles.field}>
              <span>رمز عبور جدید</span>
              <input
                type="password"
                autoComplete="new-password"
                dir="ltr"
                required
                minLength={MIN_PASSWORD_LENGTH}
                maxLength={MAX_PASSWORD_LENGTH}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <small>حداقل {fa(MIN_PASSWORD_LENGTH)} کاراکتر</small>
            </label>
          )}
          <div className={styles.dialogActions}>
            <button
              type="button"
              className={styles.button}
              disabled={busy}
              onClick={() => {
                setAction(null);
                setPassword("");
              }}
            >
              بازگشت
            </button>
            <button
              type="submit"
              className={
                action === "delete" ? styles.dangerButton : styles.primaryButton
              }
              disabled={busy}
            >
              {busy ? "در حال انجام…" : `تأیید ${titles[action]}`}
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}

export default function AdminUsers() {
  const { user: currentUser } = useAppState();
  const [term, setTerm] = useState("");
  const [appliedTerm, setAppliedTerm] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [notice, setNotice] = useState({ text: "", ok: false });
  const [selected, setSelected] = useState<AdminUserRow | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [pending, setPending] = useState<(() => Promise<void>) | null>(null);
  const [readReauthDismissed, setReadReauthDismissed] = useState(false);
  const users = useApi(
    `admin-users:${appliedTerm}:${role}:${status}:${page}`,
    (signal) =>
      apiGet<AdminUserPage>(
        "/admin/users",
        {
          term: appliedTerm || undefined,
          role: role || undefined,
          is_active: status === "" ? undefined : status === "active",
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        },
        signal,
      ),
  );
  const clearFilters = () => {
    setTerm("");
    setAppliedTerm("");
    setRole("");
    setStatus("");
    setPage(0);
  };
  const guarded = async (action: () => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setNotice({ text: "", ok: false });
    try {
      await action();
    } catch (error) {
      if (needsReauth(error)) {
        setPending(() => action);
        return;
      }
      setSelected(null);
      setNotice({
        text:
          error instanceof ApiError
            ? (ADMIN_ERROR_TEXT[error.code] ??
              "انجام عملیات ممکن نشد. دوباره تلاش کنید.")
            : "ارتباط با سرور برقرار نشد.",
        ok: false,
      });
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };
  const perform = (row: AdminUserRow, action: Action, password: string) =>
    void guarded(async () => {
      await applyUserAction(row, action, password);
      setSelected(null);
      setNotice({
        text: SUCCESS_MESSAGES[action],
        ok: true,
      });
      if (action === "password" && currentUser?.id === row.id) {
        // A full reload discards the now-invalid AppState session after token revocation.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/login?next=%2Fadmin%2Fusers");
        return;
      }
      if (
        page > 0 &&
        users.data?.items.length === 1 &&
        (action === "delete" ||
          (action === "role" && role) ||
          (action === "status" && status))
      )
        setPage(page - 1);
      else users.retry();
    });
  const filtered = Boolean(appliedTerm || role || status);
  function renderUserList() {
    if (users.loading) return (
          <LoadingState />
        );
    if (users.error) return (
          <EmptyState
            title="دریافت کاربران انجام نشد"
            description="اتصال را بررسی کنید و دوباره تلاش کنید."
          >
            <button
              className={styles.button}
              onClick={() => {
                setReadReauthDismissed(false);
                users.retry();
              }}
            >
              تلاش دوباره
            </button>
          </EmptyState>
        );
    if (!users.data?.items.length) return (
          <EmptyState
            title={
              filtered
                ? "کاربری با این مشخصات پیدا نشد"
                : "کاربری برای نمایش وجود ندارد"
            }
            description={
              filtered
                ? "عبارت جست‌وجو یا فیلترها را تغییر دهید."
                : "حساب‌های ثبت‌شده در این بخش نمایش داده می‌شوند."
            }
          >
            {filtered && (
              <button className={styles.button} onClick={clearFilters}>
                پاک کردن فیلترها
              </button>
            )}
          </EmptyState>
        );
    return (
          <section
            className={styles.tableScroll}
            aria-label="جدول کاربران"
          >
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">کاربر</th>
                  <th scope="col">نقش</th>
                  <th scope="col">وضعیت</th>
                  <th scope="col">تاریخ عضویت</th>
                  <th scope="col">آخرین ورود</th>
                  <th scope="col">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <div className={styles.userCell}>
                        <span
                          className={styles.avatar}
                          data-admin={row.role === "admin"}
                        >
                          {row.email.slice(0, 1).toUpperCase()}
                        </span>
                        <div>
                          <span className={styles.email} dir="ltr">
                            {row.email}
                          </span>
                          {currentUser?.id === row.id && (
                            <small>حساب شما</small>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span
                        className={
                          row.role === "admin"
                            ? styles.adminBadge
                            : styles.roleBadge
                        }
                      >
                        {row.role === "admin" && (
                          <AdminIcon name="shield" size={13} />
                        )}
                        {row.role === "admin" ? "مدیر" : "کاربر"}
                      </span>
                    </td>
                    <td>
                      <span
                        className={
                          row.is_active
                            ? styles.activeBadge
                            : styles.inactiveBadge
                        }
                      >
                        <i />
                        {row.is_active ? "فعال" : "غیرفعال"}
                      </span>
                    </td>
                    <td className={styles.dateCell}>
                      {adminDate(row.created_at)}
                    </td>
                    <td className={styles.dateCell}>
                      {row.last_login_at
                        ? adminDate(row.last_login_at, true)
                        : "هنوز وارد نشده"}
                    </td>
                    <td>
                      <button
                        className={styles.manageButton}
                        aria-label={`مدیریت ${row.email}`}
                        onClick={() => setSelected(row)}
                      >
                        <AdminIcon name="settings" size={15} />
                        مدیریت
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        );
  }
  return (
    <>
      <PageHeading
        title="مدیریت کاربران"
        description="حساب‌های کاربری، سطح دسترسی و وضعیت فعالیت را مدیریت کنید."
      >
        <RefreshButton loading={users.loading} onClick={users.retry} />
      </PageHeading>
      {notice.text && (
        <output
          className={notice.ok ? styles.success : styles.error}
        >
          {notice.text}
          <button
            className={styles.iconButton}
            aria-label="بستن پیام"
            onClick={() => setNotice({ text: "", ok: false })}
          >
            <AdminIcon name="close" size={16} />
          </button>
        </output>
      )}
      <section className={styles.panel}>
        <div className={styles.panelHeading}>
          <div className={styles.inlineHeading}>
            <h2>فهرست کاربران</h2>
            {users.data && (
              <span className={styles.countBadge}>
                {fa(users.data.total)} کاربر
              </span>
            )}
          </div>
          <span className={styles.muted}>مدیریت دسترسی‌ها</span>
        </div>
        <div className={styles.toolbar}>
          <form
            className={styles.search}
            onSubmit={(event) => {
              event.preventDefault();
              setPage(0);
              setAppliedTerm(term.trim());
            }}
          >
            <Icon name="search" size={18} />
            <input
              aria-label="جست‌وجوی ایمیل"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="جست‌وجو با ایمیل کاربر…"
            />
            <button className={styles.primaryButton} type="submit">
              جست‌وجو
            </button>
          </form>
          <label className={styles.filterLabel}>
            <span>نقش</span>
            <select
              value={role}
              onChange={(event) => {
                setRole(event.target.value);
                setPage(0);
              }}
            >
              <option value="">همه نقش‌ها</option>
              <option value="admin">مدیر</option>
              <option value="user">کاربر</option>
            </select>
          </label>
          <label className={styles.filterLabel}>
            <span>وضعیت</span>
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(0);
              }}
            >
              <option value="">همه وضعیت‌ها</option>
              <option value="active">فعال</option>
              <option value="inactive">غیرفعال</option>
            </select>
          </label>
          {filtered && (
            <button className={styles.textButton} onClick={clearFilters}>
              پاک کردن فیلترها
            </button>
          )}
        </div>
        {renderUserList()}
        {users.data && (
          <Pagination
            total={users.data.total}
            page={page}
            size={PAGE_SIZE}
            onChange={setPage}
          />
        )}
      </section>
      <p className={styles.footnote}>
        <AdminIcon name="shield" size={15} />
        تغییر نقش، وضعیت و حذف حساب خودتان امکان‌پذیر نیست. همه تغییرات ثبت
        می‌شوند.
      </p>
      {selected && (
        <UserActions
          key={selected.id}
          row={selected}
          self={selected.id === currentUser?.id}
          busy={busy}
          onClose={() => setSelected(null)}
          onAction={(action, password) => perform(selected, action, password)}
        />
      )}
      <ReauthPrompt
        open={pending !== null}
        onCancel={() => setPending(null)}
        onDone={() => {
          const retry = pending;
          setPending(null);
          if (retry) void guarded(retry);
        }}
      />
      <ReauthPrompt
        open={needsReauth(users.error) && !readReauthDismissed}
        onCancel={() => setReadReauthDismissed(true)}
        onDone={() => {
          setReadReauthDismissed(false);
          users.retry();
        }}
      />
    </>
  );
}
