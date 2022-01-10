create proc todo_create_tables()
begin

  -- All non-null cgsql column types
  create table a (
    t text not null,
    b bool not null,
    i integer not null,
    l long not null,
    r real not null,
    bl blob not null
  );

  -- All nullable cgsql column types
  create table b(
    t text,
    b bool,
    i integer,
    l long,
    r real,
    bl blob
  );

end;

create proc a_add(t text not null, b bool not null, i integer not null, l long not null, r real not null, bl blob not null)
begin
  insert into a values(t, b, i, l, r, bl);
end;

create proc b_add(t text, b bool, i integer, l long, r real, bl blob)
begin
  insert into b values(t, b, i, l, r, bl);
end;

create proc all_a()
begin
  select rowid, t, b, i, l, r, bl from a order by rowid;
end;

create proc all_b()
begin
  select rowid, t, b, i, l, r, bl from b order by rowid;
end;

create proc a_with_args(t_ text, b_ bool, i_ integer, l_ long, r_ real, bl_ blob, t2_ text not null, b2_ bool not null, i2_ integer not null, l2_ long not null, r2_ real not null, bl2_ blob not null)
begin
  select rowid, t, b, i, l, r, bl from a where instr(t, t_) > 0 order by rowid;
end;


create proc a_set_b(rowid_ integer not null, b_ bool not null)
begin
  update a set b = b_ where rowid == rowid_;
end;

create proc a_delete(rowid_ integer not null)
begin
  delete from a where rowid == rowid_;
end;

create proc test_objects(out dest object, out dest2 object not null, src object, src2 object not null)
begin
  set dest := src;
  set dest2 := src2;
end;

create proc test_out(output_row bool not null)
begin
  declare C cursor like select 1 value;
  fetch C from values(17);
  if output_row then
    out C;
  end if;
end;


-- Returns integers 0..n
create proc fetch_range(n integer not null)
begin
  declare C cursor like select 1 value;
  declare i integer not null;
  set i := 0;
  while (i < n)
  begin
     -- emit one row for every integer
     fetch C from values(i);
     out union C;
     set i := i + 1;
  end;
end;