import { describe, it, expect } from 'vitest'
import { filterOrdersBySearchAndStatus, uniqueOrderStatuses } from './orderListFilters'

describe('orderListFilters', () => {
  const rows = [
    { order_id: '100', status: 'Shipped', x: 1 },
    { order_id: '200', status: 'Created', x: 2 },
    { order_id: '1100', status: 'Created', x: 3 },
  ]

  it('filterOrdersBySearchAndStatus filters by id substring', () => {
    expect(filterOrdersBySearchAndStatus(rows, '10', 'all')).toHaveLength(2)
    expect(filterOrdersBySearchAndStatus(rows, '200', 'all')).toHaveLength(1)
  })

  it('filterOrdersBySearchAndStatus filters by status', () => {
    expect(filterOrdersBySearchAndStatus(rows, '', 'Created')).toHaveLength(2)
    expect(filterOrdersBySearchAndStatus(rows, '', 'Shipped')).toHaveLength(1)
  })

  it('uniqueOrderStatuses returns sorted unique', () => {
    expect(uniqueOrderStatuses(rows)).toEqual(['Created', 'Shipped'])
  })
})
