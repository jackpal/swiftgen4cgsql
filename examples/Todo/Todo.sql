create proc tasks_create_tables()
begin

  create table tasks (
    description text not null,
    done bool default false not null
  );

end;

create proc tasks_add(description text not null, done bool not null)
begin
  insert into tasks values(description, done);
end;

create proc tasks_all()
begin
  select * from tasks order by rowid;
end;

create proc tasks_set_done(rowid_ integer not null, done_ bool not null)
begin
  update tasks set done = done_ where rowid == rowid_;
end;

create proc tasks_delete(rowid_ integer not null)
begin
  delete from tasks where rowid == rowid_;
end;
