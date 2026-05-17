import { Pool } from 'pg';
import dotenv from 'dotenv';

dotenv.config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

pool.on('error', (err) => {
  console.error('Unexpected error on idle client', err);
  process.exit(-1);
});

export const initDatabase = async (): Promise<void> => {
  const client = await pool.connect();
  try {
    // Create users table
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(255) NOT NULL,
        role VARCHAR(20) DEFAULT 'user',
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Add role, is_active, and profile_picture columns if they don't exist (for existing databases)
    await client.query(`
      DO $$
      BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'role') THEN
          ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'is_active') THEN
          ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT true;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'profile_picture') THEN
          ALTER TABLE users ADD COLUMN profile_picture VARCHAR(500);
        END IF;
      END $$;
    `);

    // Create analyses table
    await client.query(`
      CREATE TABLE IF NOT EXISTS analyses (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        original_text TEXT NOT NULL,
        title VARCHAR(255),
        word_count INTEGER,
        sentence_count INTEGER,
        avg_sentence_length DECIMAL,
        avg_syllables_per_word DECIMAL,
        flesch_reading_ease DECIMAL,
        flesch_kincaid_grade DECIMAL,
        automated_readability_index DECIMAL,
        smog_readability DECIMAL,
        coleman_liau_index DECIMAL,
        predicted_grade_level VARCHAR(50),
        predicted_complexity VARCHAR(50),
        confidence DECIMAL,
        raw_score DECIMAL,
        model_predictions JSONB,
        model_breakdown JSONB,
        difficult_words_count INTEGER,
        difficult_words_percentage DECIMAL,
        difficult_words JSONB,
        difficult_sentences JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create indexes
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id)
    `);
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)
    `);

    await client.query(`
      ALTER TABLE analyses
      ADD COLUMN IF NOT EXISTS raw_score DECIMAL,
      ADD COLUMN IF NOT EXISTS model_predictions JSONB,
      ADD COLUMN IF NOT EXISTS model_breakdown JSONB
    `);

    // Create simplification_history table
    await client.query(`
      CREATE TABLE IF NOT EXISTS simplification_history (
        id SERIAL PRIMARY KEY,
        analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        original_text TEXT NOT NULL,
        simplified_text TEXT NOT NULL,
        target_grade VARCHAR(50) NOT NULL,
        changes_applied JSONB NOT NULL,
        mode VARCHAR(20) NOT NULL CHECK (mode IN ('auto', 'interactive')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_simplification_user ON simplification_history(user_id)
    `);
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_simplification_analysis ON simplification_history(analysis_id)
    `);

    // Add metrics columns to simplification_history if they don't exist
    await client.query(`
      ALTER TABLE simplification_history
      ADD COLUMN IF NOT EXISTS metrics_original JSONB,
      ADD COLUMN IF NOT EXISTS metrics_simplified JSONB
    `);

    // Create RAG tables
    await client.query(`
      CREATE TABLE IF NOT EXISTS rag_documents (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        filename VARCHAR(255) NOT NULL,
        original_filename VARCHAR(255) NOT NULL,
        file_size_bytes INTEGER,
        total_pages INTEGER,
        total_chunks INTEGER,
        chromadb_collection_id VARCHAR(255) NOT NULL UNIQUE,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS rag_queries (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        query_text TEXT NOT NULL,
        document_ids TEXT[],
        result_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Migrate document_ids column from INTEGER[] to TEXT[] if needed
    await client.query(`
      DO $$
      BEGIN
        IF EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_name = 'rag_queries' AND column_name = 'document_ids' AND data_type = 'ARRAY' AND udt_name = '_int4'
        ) THEN
          ALTER TABLE rag_queries ALTER COLUMN document_ids TYPE TEXT[] USING document_ids::TEXT[];
        END IF;
      END $$;
    `);

    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rag_docs_user ON rag_documents(user_id)
    `);
    await client.query(`
      CREATE INDEX IF NOT EXISTS idx_rag_queries_user ON rag_queries(user_id)
    `);

    // Add concept_graph column to analyses and rag_documents
    await client.query(`
      DO $$
      BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'analyses' AND column_name = 'concept_graph') THEN
          ALTER TABLE analyses ADD COLUMN concept_graph JSONB;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rag_documents' AND column_name = 'concept_graph') THEN
          ALTER TABLE rag_documents ADD COLUMN concept_graph JSONB;
        END IF;
      END $$;
    `);

    console.log('Database tables initialized successfully');
  } catch (error) {
    console.error('Error initializing database:', error);
    throw error;
  } finally {
    client.release();
  }
};

export default pool;
