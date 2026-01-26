-- ett_org
--   │              │
--   ▼              ▼
-- ett_customer   ett_location
--   │              │
--   ▼              ▼
-- ett_project    ett_person
--   │   ▲           ▲
--   │   └───────────┘
--   │        (via org_cd, prsn_cd in ett_proj_team)
--   ▼
-- ett_task
--   │   ▲
--   │   └───────────┐
--   ▼               │
-- ett_proj_team ────┘
--       │
--       ▼
--  ett_proj_timelog

-- Key FKs:
-- ett_customer.org_cd                → ett_org.org_cd
-- ett_project.(org_cd, cust_cd)      → ett_customer.(org_cd, cust_cd)
-- ett_task.(org_cd, proj_cd)         → ett_project.(org_cd, proj_cd)
-- ett_location.org_cd                → ett_org.org_cd
-- ett_person.(org_cd, loc_cd)        → ett_location.(org_cd, loc_cd)
-- ett_proj_team.(org_cd, proj_cd)    → ett_project.(org_cd, proj_cd)
-- ett_proj_team.(org_cd, prsn_cd)    → ett_person.(org_cd, prsn_cd)
-- ett_proj_timelog.(org_cd, prsn_cd, proj_cd)
--                                    → ett_proj_team.(org_cd, prsn_cd, proj_cd)
-- ett_proj_timelog.(org_cd, proj_cd, task_cd)
--                                    → ett_task.(org_cd, proj_cd, task_cd)
-- drop table if exists ett_proj_timelog cascade;
-- drop table if exists ett_proj_team cascade;
-- drop table if exists ett_project cascade;
-- drop table if exists ett_task cascade;
-- drop table if exists ett_customer cascade;
-- drop table if exists ett_location cascade;
-- drop table if exists ett_person cascade;
-- drop table if exists ett_org cascade;

CREATE TABLE 
    ett_org 
    ( 
        org_cd      CHARACTER VARYING(50) NOT NULL, 
        org_nm      CHARACTER VARYING(200) NOT NULL, 
        org_desc    CHARACTER VARYING(500) NOT NULL, 
        crt_by_user CHARACTER VARYING(50) NOT NULL, 
        upd_by_user CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        org_cidrs   CHARACTER VARYING(2000), 
        PRIMARY KEY (org_cd) 
    );

CREATE TABLE 
    ett_customer 
    ( 
        org_cd      CHARACTER VARYING(50) NOT NULL, 
        cust_cd     CHARACTER VARYING(50) NOT NULL, 
        cust_nm     CHARACTER VARYING(200) NOT NULL, 
        cust_desc   CHARACTER VARYING(500) NOT NULL, 
        cust_status CHARACTER VARYING(50) NOT NULL, 
        crt_by_user CHARACTER VARYING(50) NOT NULL, 
        upd_by_user CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        PRIMARY KEY (org_cd, cust_cd),
        CONSTRAINT fk_ett_customer FOREIGN KEY (org_cd)
            REFERENCES ett_org (org_cd)
    );
    
        
CREATE TABLE 
    ett_project 
    ( 
        org_cd       CHARACTER VARYING(50) NOT NULL, 
        proj_cd      CHARACTER VARYING(50) NOT NULL, 
        proj_nm      CHARACTER VARYING(200) NOT NULL, 
        proj_desc    CHARACTER VARYING(500) NOT NULL, 
        cust_cd      CHARACTER VARYING(50) NOT NULL, 
        proj_est_hrs NUMERIC(12,3) NOT NULL, 
        proj_act_hrs NUMERIC(12,3) NOT NULL, 
        proj_inv_hrs NUMERIC(12,3) NOT NULL, 
        proj_acc_hrs NUMERIC(12,3) NOT NULL, 
        proj_status  CHARACTER VARYING(50) NOT NULL, 
        crt_by_user  CHARACTER VARYING(50) NOT NULL, 
        upd_by_user  CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts    TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts    TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        PRIMARY KEY (org_cd, proj_cd),
        CONSTRAINT fk_ett_project FOREIGN KEY (org_cd, cust_cd)
            REFERENCES ett_customer (org_cd, cust_cd)    
    );
    
CREATE TABLE 
    ett_task 
    ( 
        org_cd       CHARACTER VARYING(50) NOT NULL, 
        proj_cd      CHARACTER VARYING(50) NOT NULL, 
        task_cd      CHARACTER VARYING(50) NOT NULL, 
        task_nm      CHARACTER VARYING(200) NOT NULL, 
        task_desc    CHARACTER VARYING(500) NOT NULL, 
        task_est_hrs NUMERIC(12,3) NOT NULL, 
        task_act_hrs NUMERIC(12,3) NOT NULL, 
        task_inv_hrs NUMERIC(12,3) NOT NULL, 
        task_acc_hrs NUMERIC(12,3) NOT NULL, 
        task_status  CHARACTER VARYING(50) NOT NULL, 
        crt_by_user  CHARACTER VARYING(50) NOT NULL, 
        upd_by_user  CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts    TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts    TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        PRIMARY KEY (org_cd, proj_cd, task_cd),
        CONSTRAINT fk_ett_task FOREIGN KEY (org_cd, proj_cd)
            REFERENCES ett_project (org_cd, proj_cd) 
    );

CREATE TABLE 
    ett_location 
    ( 
        org_cd      CHARACTER VARYING(50) NOT NULL, 
        loc_cd      CHARACTER VARYING(50) NOT NULL, 
        loc_nm      CHARACTER VARYING(200) NOT NULL, 
        loc_desc    CHARACTER VARYING(500) NOT NULL, 
        loc_locale  CHARACTER VARYING(50) NOT NULL, 
        loc_tz      CHARACTER VARYING(50) NOT NULL, 
        loc_cntry   CHARACTER VARYING(50) NOT NULL, 
        loc_state   CHARACTER VARYING(50) NOT NULL, 
        crt_by_user CHARACTER VARYING(50) NOT NULL, 
        upd_by_user CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        PRIMARY KEY (org_cd, loc_cd),
        CONSTRAINT fk_ett_location FOREIGN KEY (org_cd)
            REFERENCES ett_org (org_cd) 
    );
    
    
CREATE TABLE 
    ett_person 
    ( 
        org_cd      CHARACTER VARYING(200) NOT NULL, 
        prsn_cd     CHARACTER VARYING(200) NOT NULL, 
        email       CHARACTER VARYING(200) NOT NULL, 
        first_nm    CHARACTER VARYING(100) NOT NULL, 
        last_nm     CHARACTER VARYING(100) NOT NULL, 
        disp_name   CHARACTER VARYING(200) NOT NULL, 
        email_alt   CHARACTER VARYING(200) NOT NULL, 
        phone_cell  CHARACTER VARYING(50) NOT NULL, 
        phone_land  CHARACTER VARYING(50) NOT NULL, 
        phone_alt   CHARACTER VARYING(50) NOT NULL, 
        loc_cd      CHARACTER VARYING(50) NOT NULL, 
        locale      CHARACTER VARYING(50) NOT NULL, 
        timezone    CHARACTER VARYING(50) NOT NULL, 
        status      CHARACTER VARYING(50) NOT NULL, 
        crt_by_user CHARACTER VARYING(50) NOT NULL, 
        upd_by_user CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        role        CHARACTER VARYING(50) DEFAULT 'user'::CHARACTER VARYING, 
        PRIMARY KEY (org_cd, prsn_cd), 
        CONSTRAINT fk_ett_person FOREIGN KEY (org_cd, loc_cd)
            REFERENCES ett_location (org_cd, loc_cd)
    );

    CREATE TABLE 
    ett_proj_team 
    ( 
        org_cd       CHARACTER VARYING(50) NOT NULL, 
        proj_cd      CHARACTER VARYING(50) NOT NULL, 
        prsn_cd      CHARACTER VARYING(50) NOT NULL, 
        role_cd      CHARACTER VARYING(50) NOT NULL, 
        prsn_est_hrs NUMERIC(12,3) NOT NULL, 
        prsn_act_hrs NUMERIC(12,3) NOT NULL, 
        prsn_inv_hrs NUMERIC(12,3) NOT NULL, 
        prsn_acc_hrs NUMERIC(12,3) NOT NULL, 
        prsn_status  CHARACTER VARYING(50) NOT NULL, 
        crt_by_user  CHARACTER VARYING(50) NOT NULL, 
        upd_by_user  CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts    TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts    TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        PRIMARY KEY (org_cd, proj_cd, prsn_cd), 
        CONSTRAINT ett_proj_team FOREIGN KEY (org_cd, proj_cd)
            REFERENCES ett_project (org_cd, proj_cd),
        CONSTRAINT ett_proj_team_1 FOREIGN KEY (org_cd, prsn_cd)
            REFERENCES ett_person (org_cd, prsn_cd)
    );

CREATE TABLE 
    ett_proj_timelog 
    ( 
        projtl_id   CHARACTER VARYING(50) NOT NULL, 
        org_cd      CHARACTER VARYING(50) NOT NULL, 
        prsn_cd     CHARACTER VARYING(50) NOT NULL, 
        clock_dt    DATE NOT NULL, 
        proj_cd     CHARACTER VARYING(50) NOT NULL, 
        task_cd     CHARACTER VARYING(50) NOT NULL, 
        task_note   CHARACTER VARYING(2048) NOT NULL, 
        time_from   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        time_to     TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        total_time  NUMERIC(12,3) NOT NULL, 
        crt_by_user CHARACTER VARYING(50) NOT NULL, 
        upd_by_user CHARACTER VARYING(50) NOT NULL, 
        crt_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        upd_by_ts   TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL, 
        PRIMARY KEY (projtl_id), 
        CONSTRAINT ett_proj_tl_ix1 UNIQUE (org_cd, prsn_cd, clock_dt, proj_cd, task_cd),
        CONSTRAINT fk_ett_proj_timelog FOREIGN KEY (org_cd, prsn_cd, proj_cd)
            REFERENCES ett_proj_team (org_cd, prsn_cd, proj_cd),
        CONSTRAINT fk_ett_proj_timelog_1 FOREIGN KEY (org_cd, proj_cd, task_cd)
            REFERENCES ett_task (org_cd, proj_cd, task_cd)
    );	
    
-- drop table if exists ett_proj_timelog cascade;
-- drop table if exists ett_proj_team cascade;
-- drop table if exists ett_project cascade;
-- drop table if exists ett_task cascade;
-- drop table if exists ett_customer cascade;
-- drop table if exists ett_location cascade;
-- drop table if exists ett_person cascade;
-- drop table if exists ett_org cascade;

SELECT COUNT(*) FROM ett_org;
SELECT COUNT(*) FROM ett_customer;
SELECT COUNT(*) FROM ett_project;
SELECT COUNT(*) FROM ett_person;
SELECT COUNT(*) FROM ett_task;
SELECT COUNT(*) FROM ett_proj_team;
SELECT COUNT(*) FROM ett_proj_timelog;