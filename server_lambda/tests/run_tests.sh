#!/bin/bash
#
# Test Runner for Javumbo Serverless Tests
#
# Usage: ./run_tests.sh [day]
#   ./run_tests.sh      # Run all tests
#   ./run_tests.sh 2    # Run only Day 2 tests
#   ./run_tests.sh 3    # Run only Day 3 tests
#   ./run_tests.sh 4    # Run only Day 4 tests
#   ./run_tests.sh 5    # Run only Day 5 tests

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

DAY=${1:-all}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Javumbo Serverless Test Runner${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if S3_BUCKET is set (for Days 2-4)
if [ "$DAY" = "all" ] || [ "$DAY" = "2" ] || [ "$DAY" = "3" ] || [ "$DAY" = "4" ]; then
    if [ -z "$S3_BUCKET" ]; then
        echo -e "${RED}ERROR: S3_BUCKET environment variable not set${NC}"
        echo ""
        echo "Run this first:"
        echo "  cd ../terraform"
        echo "  export S3_BUCKET=\$(terraform output -raw s3_bucket_name)"
        echo "  cd ../tests"
        exit 1
    fi
    echo -e "Using S3 bucket: ${GREEN}$S3_BUCKET${NC}"
fi

# Check if DYNAMODB_USERS_TABLE is set (for Day 5)
if [ "$DAY" = "all" ] || [ "$DAY" = "5" ]; then
    if [ -z "$DYNAMODB_USERS_TABLE" ]; then
        echo -e "${RED}ERROR: DYNAMODB_USERS_TABLE environment variable not set${NC}"
        echo ""
        echo "Run this first:"
        echo "  cd ../terraform"
        echo "  export DYNAMODB_USERS_TABLE=\$(terraform output -raw dynamodb_users_table_name)"
        echo "  cd ../tests"
        exit 1
    fi
    echo -e "Using DynamoDB users table: ${GREEN}$DYNAMODB_USERS_TABLE${NC}"
fi

echo ""

# Run Day 2 tests if requested
if [ "$DAY" = "all" ] || [ "$DAY" = "2" ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Day 2: S3SQLiteConnection Tests${NC}"
    echo -e "${YELLOW}========================================${NC}\n"

# Run Test 2.1
echo -e "${YELLOW}Running Test 2.1: New User Database Creation${NC}"
python3 test_s3_sqlite_new_user.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test 2.1 passed${NC}\n"
else
    echo -e "${RED}✗ Test 2.1 failed${NC}\n"
    exit 1
fi

# Run Test 2.2
echo -e "${YELLOW}Running Test 2.2: Read/Write Persistence${NC}"
python3 test_s3_sqlite_readwrite.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test 2.2 passed${NC}\n"
else
    echo -e "${RED}✗ Test 2.2 failed${NC}\n"
    exit 1
fi

# Run Test 2.3
echo -e "${YELLOW}Running Test 2.3: Latency Baseline Measurement${NC}"
python3 test_s3_sqlite_latency.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test 2.3 passed${NC}\n"
else
    echo -e "${RED}✗ Test 2.3 failed${NC}\n"
    exit 1
fi
fi

# Run Day 3 tests if requested
if [ "$DAY" = "all" ] || [ "$DAY" = "3" ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Day 3: Caching Tests${NC}"
    echo -e "${YELLOW}========================================${NC}\n"

    # Run Test 3.1
    echo -e "${YELLOW}Running Test 3.1: Cache Speedup${NC}"
    python3 test_s3_sqlite_cache.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 3.1 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 3.1 failed${NC}\n"
        exit 1
    fi

    # Run Test 3.2
    echo -e "${YELLOW}Running Test 3.2: Cache Hit Rate (50 requests)${NC}"
    python3 test_s3_sqlite_cache_hitrate.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 3.2 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 3.2 failed${NC}\n"
        exit 1
    fi
fi

# Run Day 4 tests if requested
if [ "$DAY" = "all" ] || [ "$DAY" = "4" ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Day 4: Conflict Detection Tests${NC}"
    echo -e "${YELLOW}========================================${NC}\n"

    # Run Test 4.1
    echo -e "${YELLOW}Running Test 4.1: Conflict Detection${NC}"
    python3 test_s3_sqlite_conflict.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 4.1 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 4.1 failed${NC}\n"
        exit 1
    fi

    # Run Test 4.2
    echo -e "${YELLOW}Running Test 4.2: Concurrent Writes (10 workers)${NC}"
    python3 test_s3_sqlite_concurrent.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 4.2 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 4.2 failed${NC}\n"
        exit 1
    fi
fi

# Run Day 5 tests if requested
if [ "$DAY" = "all" ] || [ "$DAY" = "5" ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Day 5: DynamoDB User Repository Tests${NC}"
    echo -e "${YELLOW}========================================${NC}\n"

    # Run Test 5.1
    echo -e "${YELLOW}Running Test 5.1: User Registration${NC}"
    python3 test_user_repository_register.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 5.1 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 5.1 failed${NC}\n"
        exit 1
    fi

    # Run Test 5.2
    echo -e "${YELLOW}Running Test 5.2: User Authentication${NC}"
    python3 test_user_repository_auth.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 5.2 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 5.2 failed${NC}\n"
        exit 1
    fi

    # Run Test 5.3
    echo -e "${YELLOW}Running Test 5.3: User CRUD Operations${NC}"
    python3 test_user_repository_crud.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Test 5.3 passed${NC}\n"
    else
        echo -e "${RED}✗ Test 5.3 failed${NC}\n"
        exit 1
    fi
fi

echo -e "${GREEN}========================================${NC}"
if [ "$DAY" = "2" ]; then
    echo -e "${GREEN}All Day 2 tests passed! ✅${NC}"
elif [ "$DAY" = "3" ]; then
    echo -e "${GREEN}All Day 3 tests passed! ✅${NC}"
elif [ "$DAY" = "4" ]; then
    echo -e "${GREEN}All Day 4 tests passed! ✅${NC}"
elif [ "$DAY" = "5" ]; then
    echo -e "${GREEN}All Day 5 tests passed! ✅${NC}"
else
    echo -e "${GREEN}All tests passed! ✅${NC}"
fi
echo -e "${GREEN}========================================${NC}\n"
