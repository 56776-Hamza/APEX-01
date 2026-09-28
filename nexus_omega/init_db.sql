-- NEXUS-OMEGA (APEX-1) Database Initialization Script
-- Enables UUID and Vector extensions and initializes all relational tables

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Agent Profiles (Swarm Roles)
CREATE TABLE IF NOT EXISTS agent_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(64) NOT NULL UNIQUE,
    role VARCHAR(64) NOT NULL,
    system_instruction TEXT NOT NULL,
    model_provider VARCHAR(32) NOT NULL DEFAULT 'openrouter',
    model_name VARCHAR(128) NOT NULL,
    temperature NUMERIC(3, 2) NOT NULL DEFAULT 0.70,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Goals & Task Kanban State Machine
DO $$ BEGIN
    CREATE TYPE task_status AS ENUM ('TODO', 'READY', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'FAILED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS goals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    success_criteria JSONB NOT NULL DEFAULT '{}',
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    goal_id UUID REFERENCES goals(id) ON DELETE CASCADE,
    parent_task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    assigned_agent_id UUID REFERENCES agent_profiles(id),
    title VARCHAR(255) NOT NULL,
    instruction TEXT NOT NULL,
    status task_status DEFAULT 'TODO',
    input_payload JSONB DEFAULT '{}',
    output_payload JSONB DEFAULT '{}',
    execution_order INT DEFAULT 1,
    requires_human_auth BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 3. Execution Logs & Tool Audit Trail
CREATE TABLE IF NOT EXISTS tool_execution_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agent_profiles(id),
    tool_name VARCHAR(64) NOT NULL,
    input_parameters JSONB NOT NULL,
    output_response TEXT,
    is_error BOOLEAN DEFAULT FALSE,
    execution_latency_ms INT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Long-Term Vector Memory
CREATE TABLE IF NOT EXISTS agent_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agent_profiles(id),
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_embedding 
ON agent_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 5. Scientific Self-Learning Ledger
CREATE TABLE IF NOT EXISTS parameter_learning_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agent_profiles(id),
    metric_name VARCHAR(64) NOT NULL,
    variable_mutated VARCHAR(64) NOT NULL,
    previous_value TEXT NOT NULL,
    mutated_value TEXT NOT NULL,
    baseline_score NUMERIC(8, 4) NOT NULL,
    observed_score NUMERIC(8, 4) NOT NULL,
    hypothesis TEXT NOT NULL,
    is_adopted BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
