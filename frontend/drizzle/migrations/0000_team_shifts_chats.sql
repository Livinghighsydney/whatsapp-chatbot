
create type public.app_role as enum ('admin', 'agent');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default '',
  email text not null default '',
  created_at timestamptz not null default now()
);
grant select, update on public.profiles to authenticated;
grant all on public.profiles to service_role;
alter table public.profiles enable row level security;

create table public.user_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  role app_role not null,
  unique (user_id, role)
);
grant select on public.user_roles to authenticated;
grant all on public.user_roles to service_role;
alter table public.user_roles enable row level security;

create or replace function public.has_role(_user_id uuid, _role app_role)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.user_roles where user_id = _user_id and role = _role)
$$;

create policy "read own or admin profiles" on public.profiles for select to authenticated
  using (id = auth.uid() or public.has_role(auth.uid(), 'admin'));
create policy "update own profile" on public.profiles for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid());
create policy "read own or admin roles" on public.user_roles for select to authenticated
  using (user_id = auth.uid() or public.has_role(auth.uid(), 'admin'));

create table public.shifts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  weekday smallint not null check (weekday between 0 and 6),
  start_time time not null,
  end_time time not null,
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.shifts to authenticated;
grant all on public.shifts to service_role;
alter table public.shifts enable row level security;
create policy "see own or admin shifts" on public.shifts for select to authenticated
  using (user_id = auth.uid() or public.has_role(auth.uid(), 'admin'));
create policy "admin manage shifts" on public.shifts for all to authenticated
  using (public.has_role(auth.uid(), 'admin')) with check (public.has_role(auth.uid(), 'admin'));

create table public.chats (
  id uuid primary key default gen_random_uuid(),
  phone text not null unique,
  name text,
  property text,
  room text,
  status text not null default 'handed_off',
  assigned_to uuid references public.profiles(id) on delete set null,
  last_message text,
  last_role text,
  last_ts timestamptz not null default now(),
  created_at timestamptz not null default now()
);
grant select, insert, update, delete on public.chats to authenticated;
grant all on public.chats to service_role;
alter table public.chats enable row level security;
create policy "see assigned or admin" on public.chats for select to authenticated
  using (assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'));
create policy "update assigned or admin" on public.chats for update to authenticated
  using (assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'))
  with check (assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'));
create policy "admin insert chats" on public.chats for insert to authenticated
  with check (public.has_role(auth.uid(), 'admin'));
create policy "delete assigned or admin" on public.chats for delete to authenticated
  using (assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'));

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.chats(id) on delete cascade,
  role text not null check (role in ('user','assistant','staff')),
  content text not null default '',
  media_path text,
  sender_id uuid,
  ts timestamptz not null default now()
);
grant select, insert on public.messages to authenticated;
grant all on public.messages to service_role;
alter table public.messages enable row level security;
create policy "read messages of visible chats" on public.messages for select to authenticated
  using (exists (select 1 from public.chats c where c.id = chat_id and (c.assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'))));
create policy "staff send to visible chats" on public.messages for insert to authenticated
  with check (role = 'staff' and sender_id = auth.uid() and exists (select 1 from public.chats c where c.id = chat_id and (c.assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'))));

create or replace function public.touch_chat() returns trigger language plpgsql security definer set search_path = public as $$
begin
  update public.chats set last_message = coalesce(nullif(new.content,''), '📎 File'), last_role = new.role, last_ts = new.ts where id = new.chat_id;
  return new;
end $$;
create trigger messages_touch_chat after insert on public.messages for each row execute function public.touch_chat();

create or replace function public.on_shift_member(_at timestamptz default now())
returns uuid language sql stable security definer set search_path = public as $$
  with t as (select (_at at time zone 'Asia/Karachi') as lt)
  select s.user_id
  from public.shifts s, t
  where (s.start_time <= s.end_time and s.weekday = extract(dow from t.lt) and t.lt::time >= s.start_time and t.lt::time < s.end_time)
     or (s.start_time > s.end_time and (
          (s.weekday = extract(dow from t.lt) and t.lt::time >= s.start_time) or
          (s.weekday = (extract(dow from t.lt)::int + 6) % 7 and t.lt::time < s.end_time)))
  group by s.user_id
  order by (select count(*) from public.chats c where c.assigned_to = s.user_id and c.status <> 'bot_active'), s.user_id
  limit 1
$$;

create or replace function public.auto_assign_chat() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.assigned_to is null then new.assigned_to := public.on_shift_member(); end if;
  return new;
end $$;
create trigger chats_auto_assign before insert on public.chats for each row execute function public.auto_assign_chat();

create or replace function public.assign_unassigned_chats() returns integer language plpgsql security definer set search_path = public as $$
declare n integer := 0; r record; m uuid;
begin
  if not public.has_role(auth.uid(), 'admin') then raise exception 'Only admins can do this'; end if;
  for r in select id from public.chats where assigned_to is null order by last_ts loop
    m := public.on_shift_member();
    exit when m is null;
    update public.chats set assigned_to = m where id = r.id;
    n := n + 1;
  end loop;
  return n;
end $$;
revoke execute on function public.assign_unassigned_chats() from public, anon;
grant execute on function public.assign_unassigned_chats() to authenticated;

create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, email) values (new.id, coalesce(new.raw_user_meta_data->>'full_name', ''), coalesce(new.email, ''));
  if not exists (select 1 from public.user_roles where role = 'admin') then
    insert into public.user_roles (user_id, role) values (new.id, 'admin');
  else
    insert into public.user_roles (user_id, role) values (new.id, 'agent');
  end if;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();

create or replace function public.admin_exists() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.user_roles where role = 'admin')
$$;
grant execute on function public.admin_exists() to anon, authenticated;

with c as (
  insert into public.chats (phone, name, property, room, status, last_ts) values
  ('923001234567', 'Ayesha Khan', 'Living High DHA', 'Room 204', 'handed_off', now() - interval '5 minutes'),
  ('923119876543', 'Bilal Ahmed', 'Living High Gulberg', 'Room 12B', 'handed_off', now() - interval '25 minutes'),
  ('923335551212', 'Sara Malik', 'Living High DHA', 'Room 310', 'collecting_info', now() - interval '1 hour'),
  ('923214447788', 'Usman Raza', 'Living High Johar Town', 'Room 7', 'handed_off', now() - interval '3 hours'),
  ('923456660011', 'Hina Tariq', 'Living High Gulberg', 'Room 15A', 'bot_active', now() - interval '1 day'),
  ('923007778899', null, null, null, 'collecting_info', now() - interval '2 days')
  returning id, phone
)
insert into public.messages (chat_id, role, content, ts)
select c.id, m.role, m.content, m.ts from c join (values
  ('923001234567','user','Hi, the AC in my room stopped working last night 😓', now() - interval '20 minutes'),
  ('923001234567','assistant','Sorry to hear that! Can you tell me your room number?', now() - interval '19 minutes'),
  ('923001234567','user','Room 204, DHA branch', now() - interval '18 minutes'),
  ('923001234567','assistant','Thanks Ayesha. I''m connecting you with our maintenance team now.', now() - interval '17 minutes'),
  ('923001234567','user','Please hurry, it''s really hot', now() - interval '5 minutes'),
  ('923119876543','user','I want to pay my rent but the bank link isn''t working', now() - interval '40 minutes'),
  ('923119876543','assistant','Let me hand you over to our accounts team who can help with payment.', now() - interval '39 minutes'),
  ('923119876543','user','Ok waiting', now() - interval '25 minutes'),
  ('923335551212','user','Is there a room available from next month?', now() - interval '70 minutes'),
  ('923335551212','assistant','Sure! Which branch are you interested in, and your budget?', now() - interval '69 minutes'),
  ('923335551212','user','DHA, around 45k', now() - interval '60 minutes'),
  ('923214447788','user','My roommate is playing loud music every night after 1am', now() - interval '4 hours'),
  ('923214447788','assistant','I understand, that sounds frustrating. I''m passing this to the house manager.', now() - interval '4 hours'),
  ('923214447788','user','Thank you, please keep my name private', now() - interval '3 hours'),
  ('923456660011','user','What time is breakfast served?', now() - interval '1 day'),
  ('923456660011','assistant','Breakfast is served from 7:30 to 10:00 am every day 🍳', now() - interval '1 day'),
  ('923007778899','user','Hello, I''d like to know the prices', now() - interval '2 days'),
  ('923007778899','assistant','Hi! May I have your name and which branch you''re looking at?', now() - interval '2 days')
) as m(phone, role, content, ts) on m.phone = c.phone;

create policy "staff upload chat media" on storage.objects for insert to authenticated
  with check (bucket_id = 'chat-media' and exists (select 1 from public.chats c where c.id::text = (storage.foldername(name))[1] and (c.assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'))));
create policy "staff read chat media" on storage.objects for select to authenticated
  using (bucket_id = 'chat-media' and exists (select 1 from public.chats c where c.id::text = (storage.foldername(name))[1] and (c.assigned_to = auth.uid() or public.has_role(auth.uid(), 'admin'))));
