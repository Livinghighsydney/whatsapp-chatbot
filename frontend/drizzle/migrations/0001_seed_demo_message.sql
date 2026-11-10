create or replace function public.seed_demo_message(_chat uuid, _text text) returns void language plpgsql security definer set search_path = public as $$
begin
  if not public.has_role(auth.uid(), 'admin') then raise exception 'Only admins can do this'; end if;
  insert into public.messages (chat_id, role, content) values (_chat, 'user', _text);
end $$;
revoke execute on function public.seed_demo_message(uuid, text) from public, anon;
grant execute on function public.seed_demo_message(uuid, text) to authenticated;